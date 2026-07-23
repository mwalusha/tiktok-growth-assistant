from datetime import (
    datetime,
    timedelta,
    timezone as datetime_timezone,
)
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import (
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse
from django.utils import timezone

from .analytics import (
    calculate_balanced_video_scores,
    confidence_for_evidence,
    get_account_analytics,
    get_daily_growth,
)
from .content_coach import (
    AIContentCoachError,
    build_prompt,
    call_llm_api,
    generate_content_ideas,
    parse_ideas,
)
from .content_calendar import (
    generate_weekly_calendar,
    parse_calendar,
)
from .content_generator import generate_personalized_content_ideas
from .chat_assistant import (
    build_account_context,
    call_chat_llm,
)
from .creator_score import (
    activity_score,
    build_score_explanations,
    engagement_trend_score,
    follower_growth_score,
    get_creator_score,
    posting_consistency_score,
)
from .models import (
    ContentIdea,
    ChatConversation,
    ChatMessage,
    PeerComparison,
    TikTokAccount,
    TikTokDailySnapshot,
    TikTokVideo,
    WeeklyReport,
)
from .peer_benchmark import build_peer_comparison
from .posting_times import (
    confidence_for_sample_size,
    format_hour,
    get_best_posting_times,
)
from .sync import (
    ensure_valid_access_token,
    extract_hashtags,
    sync_tiktok_performance,
)
from .viral_predictor import (
    ViralPredictionError,
    score_draft,
)
from .trend_hunter import get_trend_hunter
from .weekly_reports import generate_weekly_report


class HashtagExtractionTests(SimpleTestCase):
    def test_extracts_unique_hashtags_in_caption_order(self):
        self.assertEqual(
            extract_hashtags(
                "Try this #TikTokTips and #growth! "
                "#tiktoktIPS #creator_101"
            ),
            ["tiktoktips", "growth", "creator_101"],
        )

    def test_empty_description_has_no_hashtags(self):
        self.assertEqual(extract_hashtags(""), [])


class ContentCoachServiceTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="coach-user",
            access_token="token",
            niche="Python education",
        )
        self.top_video = TikTokVideo.objects.create(
            account=self.account,
            video_id="top-video",
            title="Loops explained",
            description="A quick Python loop tutorial",
            hashtags=["Python", "LearnToCode"],
            duration=18,
            view_count=5000,
            like_count=500,
            comment_count=50,
            share_count=100,
            posted_at=timezone.now() - timedelta(days=10),
        )
        self.recent_video = TikTokVideo.objects.create(
            account=self.account,
            video_id="recent-video",
            title="Functions explained",
            description="Three function mistakes",
            hashtags=["PythonTips"],
            duration=22,
            view_count=1000,
            posted_at=timezone.now(),
        )

    def valid_payload(self):
        return {
            "ideas": [
                {
                    "title": f"Idea {number}",
                    "hook": f"Hook {number}",
                    "caption": f"Caption {number}",
                    "hashtags": [
                        "Python",
                        "#Coding",
                        "StudentTips",
                    ],
                    "why_it_fits": "Tutorials perform well.",
                }
                for number in range(1, 6)
            ]
        }

    def test_prompt_contains_niche_top_and_recent_context(self):
        prompt = build_prompt(
            [self.top_video],
            [self.recent_video],
            self.account.niche,
        )

        self.assertIn("Python education", prompt)
        self.assertIn("Loops explained", prompt)
        self.assertIn("Functions explained", prompt)
        self.assertIn("untrusted creator data", prompt)

    @patch("tiktok_auth.content_coach.call_llm_api")
    def test_generate_returns_validated_structured_ideas(
        self,
        call_api,
    ):
        import json

        call_api.return_value = json.dumps(
            self.valid_payload()
        )

        ideas = generate_content_ideas(self.account)

        self.assertEqual(len(ideas), 5)
        self.assertEqual(
            ideas[0]["hashtags_text"],
            "#Python #Coding #StudentTips",
        )
        self.assertIn("seconds", ideas[0]["suggested_length"])
        self.assertIn(
            "UTC",
            ideas[0]["suggested_posting_time"],
        )
        prompt = call_api.call_args.args[0]
        self.assertIn("Loops explained", prompt)
        self.assertIn("Functions explained", prompt)

    def test_parse_rejects_wrong_number_of_ideas(self):
        with self.assertRaises(AIContentCoachError):
            parse_ideas('{"ideas": []}')

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-test",
        OPENAI_TIMEOUT_SECONDS=10,
    )
    @patch("tiktok_auth.content_coach.requests.post")
    def test_api_call_requests_strict_json_schema(
        self,
        post,
    ):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"ideas": []}',
                        }
                    ],
                }
            ]
        }
        post.return_value = response

        output = call_llm_api("prompt")

        self.assertEqual(output, '{"ideas": []}')
        request_payload = post.call_args.kwargs["json"]
        response_format = request_payload["text"]["format"]
        self.assertEqual(
            response_format["type"],
            "json_schema",
        )
        self.assertTrue(response_format["strict"])
        self.assertEqual(request_payload["model"], "gpt-test")


class ContentCoachViewTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="coach-view-user",
            access_token="token",
        )
        session = self.client.session
        session["tiktok_account_id"] = self.account.pk
        session.save()

    @patch("tiktok_auth.views.generate_content_ideas")
    def test_generation_is_synchronous_and_renders_ideas(
        self,
        generate,
    ):
        generate.return_value = [
            {
                "title": "A grounded idea",
                "hook": "Stop making this mistake",
                "caption": "Try this instead.",
                "hashtags_text": "#Python #Tips #Learn",
                "why_it_fits": "Your tutorials get the most views.",
            }
        ]

        response = self.client.post(
            reverse("content-coach"),
            {"niche": "Python for beginners"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A grounded idea")
        self.account.refresh_from_db()
        self.assertEqual(
            self.account.niche,
            "Python for beginners",
        )
        generate.assert_called_once()

    def test_saves_selected_generated_idea_to_planner(self):
        response = self.client.post(
            reverse("save-generated-idea"),
            {
                "title": "Saved AI idea",
                "hook": "A compelling hook",
                "caption": "A concise caption",
                "hashtags": "#Python #Tips #Learn",
            },
        )

        self.assertRedirects(
            response,
            reverse("content-planner"),
        )
        idea = ContentIdea.objects.get(
            account=self.account,
            title="Saved AI idea",
        )
        self.assertEqual(
            idea.notes,
            "Generated by the AI content coach.",
        )

    def test_generate_endpoint_saves_complete_batch(self):
        TikTokVideo.objects.create(
            account=self.account,
            video_id="coach-history",
            title="Hair transformation",
            description="Before and after #transformation",
            duration=18,
            view_count=1000,
            like_count=100,
            posted_at=timezone.now(),
        )
        response = self.client.post(
            reverse("generate-content-ideas")
        )

        self.assertRedirects(
            response,
            reverse("content-planner"),
        )
        self.assertEqual(
            self.account.content_ideas.count(),
            5,
        )
        saved = self.account.content_ideas.first()
        self.assertTrue(saved.is_generated)
        self.assertTrue(saved.generation_reason)
        self.assertEqual(
            saved.suggested_length,
            "11–20 seconds",
        )


class ViralPredictorTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="predictor-user",
            access_token="token",
        )

        for index, length in enumerate((80, 90, 100, 110)):
            TikTokVideo.objects.create(
                account=self.account,
                video_id=f"predictor-{index}",
                description="x" * length,
                hashtags=["one", "two", "three"],
                view_count=1000 - index,
            )

    def test_scores_draft_against_personal_history(self):
        result = score_draft(
            self.account,
            "x" * 95,
            "#One #Two #Three",
        )

        self.assertEqual(result["score"], 100)
        self.assertFalse(result["trending_available"])
        self.assertIn(
            "not a guarantee",
            result["disclaimer"],
        )

    def test_optional_trending_factor_matches_hashtags(self):
        result = score_draft(
            self.account,
            "x" * 95,
            "#One #Trend",
            trending_hashtags=["#Trend"],
        )

        self.assertTrue(result["trending_available"])
        self.assertEqual(result["trending_matches"], ["trend"])

    def test_requires_enough_historical_videos(self):
        self.account.videos.all().delete()

        with self.assertRaises(ViralPredictionError):
            score_draft(self.account, "caption", "#tag")


class ContentCalendarTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="calendar-user",
            access_token="token",
            niche="Python education",
        )
        TikTokVideo.objects.create(
            account=self.account,
            video_id="calendar-context",
            title="Python tips",
            description="Three loop mistakes",
            view_count=1000,
            posted_at=timezone.now(),
        )

    def calendar_payload(self):
        types = [
            "educational",
            "tutorial",
            "transformation",
            "story",
            "community",
            "promotional",
            "educational",
        ]
        return {
            "days": [
                {
                    "day_index": index,
                    "content_type": content_type,
                    "title": f"Day {index}",
                    "hook": f"Hook {index}",
                    "caption": f"Caption {index}",
                    "hashtags": ["Python", "Tips", "Learn"],
                    "why_it_fits": "Based on tutorial performance.",
                }
                for index, content_type in enumerate(types)
            ]
        }

    @patch(
        "tiktok_auth.content_calendar.call_structured_llm"
    )
    def test_generates_seven_days_and_rerun_updates(
        self,
        call_llm,
    ):
        import json

        call_llm.return_value = json.dumps(
            self.calendar_payload()
        )
        week_start = timezone.localdate() + timedelta(days=7)

        first = generate_weekly_calendar(
            self.account,
            week_start,
        )
        second = generate_weekly_calendar(
            self.account,
            week_start,
        )

        self.assertEqual(len(first["ideas"]), 7)
        self.assertEqual(len(second["ideas"]), 7)
        self.assertEqual(
            self.account.content_ideas.filter(
                calendar_date__range=(
                    week_start,
                    week_start + timedelta(days=6),
                )
            ).count(),
            7,
        )

    def test_rejects_adjacent_duplicate_content_types(self):
        import json

        payload = self.calendar_payload()
        payload["days"][1]["content_type"] = "educational"

        with self.assertRaises(AIContentCoachError):
            parse_calendar(json.dumps(payload))


class WeeklyReportTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="report-user",
            access_token="token",
        )
        self.week_start = timezone.localdate() - timedelta(
            days=timezone.localdate().weekday() + 7
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=self.week_start,
            follower_count=100,
            total_views=1000,
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=self.week_start + timedelta(days=6),
            follower_count=125,
            total_views=1800,
        )
        self.best = TikTokVideo.objects.create(
            account=self.account,
            video_id="weekly-best",
            title="Best",
            view_count=1000,
            posted_at=timezone.make_aware(
                datetime.combine(
                    self.week_start + timedelta(days=2),
                    datetime.min.time(),
                )
            ),
        )
        self.worst = TikTokVideo.objects.create(
            account=self.account,
            video_id="weekly-worst",
            title="Worst",
            view_count=100,
            posted_at=timezone.make_aware(
                datetime.combine(
                    self.week_start + timedelta(days=3),
                    datetime.min.time(),
                )
            ),
        )

    @patch("tiktok_auth.weekly_reports.get_creator_score")
    def test_report_is_idempotent_and_summarizes_week(
        self,
        creator_score,
    ):
        creator_score.return_value = {
            "score": 70,
            "components": {
                "posting_consistency": 80,
                "engagement_trend": 60,
                "follower_growth": 70,
                "activity": 50,
            },
        }

        report, created = generate_weekly_report(
            self.account,
            self.week_start,
        )
        updated_report, updated_created = generate_weekly_report(
            self.account,
            self.week_start,
        )

        self.assertTrue(created)
        self.assertFalse(updated_created)
        self.assertEqual(report.pk, updated_report.pk)
        self.assertEqual(WeeklyReport.objects.count(), 1)
        self.assertEqual(
            report.snapshot_deltas["follower_count"],
            25.0,
        )
        self.assertEqual(report.best_video, self.best)
        self.assertEqual(report.worst_video, self.worst)
        self.assertIn("Publish again", report.recommendation)


class WeeklyReportCommandTests(TestCase):
    def setUp(self):
        TikTokAccount.objects.create(
            open_id="weekly-command-1",
            access_token="token",
        )
        TikTokAccount.objects.create(
            open_id="weekly-command-2",
            access_token="token",
        )

    @patch(
        "tiktok_auth.management.commands.generate_weekly_reports."
        "generate_weekly_report"
    )
    def test_generates_report_for_every_account(self, generate):
        generate.side_effect = [
            (
                SimpleNamespace(
                    week_start=timezone.localdate()
                ),
                True,
            ),
            (
                SimpleNamespace(
                    week_start=timezone.localdate()
                ),
                False,
            ),
        ]

        call_command(
            "generate_weekly_reports",
            stdout=StringIO(),
        )

        self.assertEqual(generate.call_count, 2)


class TrendHunterTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="trend-account-1",
            access_token="token",
            niche="Python",
            allow_trend_aggregation=True,
        )
        self.peer = TikTokAccount.objects.create(
            open_id="trend-account-2",
            access_token="token",
            niche="Python",
            allow_trend_aggregation=True,
        )

    def create_trend_video(self, account, video_id, hashtags):
        return TikTokVideo.objects.create(
            account=account,
            video_id=video_id,
            hashtags=hashtags,
            view_count=1000,
            like_count=100,
            posted_at=timezone.now(),
        )

    def test_aggregates_only_shared_opted_in_hashtags(self):
        self.create_trend_video(
            self.account,
            "trend-video-1",
            ["Python", "OnlyMe"],
        )
        self.create_trend_video(
            self.peer,
            "trend-video-2",
            ["Python", "OnlyPeer"],
        )

        result = get_trend_hunter(self.account)

        self.assertEqual(
            [item["normalized"] for item in result["trends"]],
            ["python"],
        )
        self.assertFalse(result["sounds_available"])

    def test_excludes_accounts_without_consent(self):
        self.peer.allow_trend_aggregation = False
        self.peer.save(
            update_fields=["allow_trend_aggregation"]
        )
        self.create_trend_video(
            self.account,
            "trend-private-1",
            ["Python"],
        )
        self.create_trend_video(
            self.peer,
            "trend-private-2",
            ["Python"],
        )

        result = get_trend_hunter(self.account)

        self.assertEqual(result["trends"], [])


class PeerBenchmarkTests(TestCase):
    def setUp(self):
        self.requester = TikTokAccount.objects.create(
            open_id="peer-requester",
            access_token="token",
            display_name="Requester",
        )
        self.peer = TikTokAccount.objects.create(
            open_id="peer-acceptor",
            access_token="token",
            display_name="Peer",
        )

    def set_session_account(self, account):
        session = self.client.session
        session["tiktok_account_id"] = account.pk
        session.save()

    def test_invitation_requires_different_account_acceptance(self):
        self.set_session_account(self.requester)
        self.client.post(reverse("peer-benchmarks"))
        comparison = PeerComparison.objects.get()

        response = self.client.post(
            reverse(
                "accept-peer-invite",
                args=[comparison.invite_token],
            )
        )

        self.assertRedirects(
            response,
            reverse("peer-benchmarks"),
        )
        comparison.refresh_from_db()
        self.assertEqual(
            comparison.status,
            PeerComparison.Status.PENDING,
        )

        self.set_session_account(self.peer)
        self.client.post(
            reverse(
                "accept-peer-invite",
                args=[comparison.invite_token],
            )
        )
        comparison.refresh_from_db()

        self.assertEqual(
            comparison.status,
            PeerComparison.Status.ACCEPTED,
        )
        self.assertEqual(comparison.peer_account, self.peer)
        self.assertTrue(
            comparison.requesting_account.allow_peer_comparison
        )
        self.peer.refresh_from_db()
        self.assertTrue(self.peer.allow_peer_comparison)

    def test_comparison_returns_relative_metrics(self):
        comparison = PeerComparison.objects.create(
            requesting_account=self.requester,
            peer_account=self.peer,
            status=PeerComparison.Status.ACCEPTED,
        )
        TikTokVideo.objects.create(
            account=self.requester,
            video_id="requester-recent",
            view_count=100,
            like_count=10,
            posted_at=timezone.now(),
        )

        result = build_peer_comparison(
            comparison,
            self.requester,
        )

        self.assertEqual(result["own"]["posts_last_28_days"], 1)
        self.assertEqual(
            result["peer_metrics"]["posts_last_28_days"],
            0,
        )


class ChatAssistantTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="chat-account",
            access_token="token",
            display_name="Chat Creator",
            follower_count=250,
        )
        TikTokVideo.objects.create(
            account=self.account,
            video_id="chat-video",
            title="Strong tutorial",
            view_count=5000,
            posted_at=timezone.now(),
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=timezone.localdate(),
            follower_count=250,
        )
        self.conversation = ChatConversation.objects.create(
            account=self.account
        )

    def test_context_contains_account_tables_and_coverage(self):
        context = build_account_context(self.account)

        self.assertEqual(context["profile"]["followers"], 250)
        self.assertEqual(len(context["videos"]), 1)
        self.assertEqual(len(context["daily_snapshots"]), 1)
        self.assertFalse(
            context["data_coverage"]["videos_truncated"]
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-test",
        OPENAI_TIMEOUT_SECONDS=10,
    )
    @patch("tiktok_auth.chat_assistant.requests.post")
    @patch("tiktok_auth.chat_assistant.build_account_context")
    def test_chat_sends_history_and_disables_provider_storage(
        self,
        context,
        post,
    ):
        context.return_value = {"profile": {"followers": 250}}
        ChatMessage.objects.create(
            conversation=self.conversation,
            role=ChatMessage.Role.USER,
            content="How did I do?",
        )
        ChatMessage.objects.create(
            conversation=self.conversation,
            role=ChatMessage.Role.ASSISTANT,
            content="You grew.",
        )
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Keep going.",
                        }
                    ],
                }
            ]
        }
        post.return_value = response

        answer = call_chat_llm(
            self.account,
            self.conversation,
            "What next?",
        )

        self.assertEqual(answer, "Keep going.")
        payload = post.call_args.kwargs["json"]
        self.assertFalse(payload["store"])
        self.assertEqual(len(payload["input"]), 3)
        self.assertEqual(
            payload["input"][-1]["content"],
            "What next?",
        )

    @patch("tiktok_auth.views.call_chat_llm")
    def test_view_persists_user_and_assistant_messages(self, call):
        call.return_value = "Your tutorial led on views."
        session = self.client.session
        session["tiktok_account_id"] = self.account.pk
        session.save()

        response = self.client.post(
            reverse("chat-assistant"),
            {"message": "What worked?"},
        )

        self.assertRedirects(
            response,
            reverse("chat-assistant"),
        )
        messages_list = list(
            self.conversation.messages.values_list(
                "role",
                "content",
            )
        )
        self.assertEqual(
            messages_list,
            [
                ("user", "What worked?"),
                ("assistant", "Your tutorial led on views."),
            ],
        )


class CreatorScoreMathTests(SimpleTestCase):
    def test_regular_posting_scores_full_consistency(self):
        as_of = timezone.localdate()
        videos = [
            SimpleNamespace(
                posted_at=timezone.now()
                - timedelta(days=days_ago)
            )
            for days_ago in (9, 6, 3, 0)
        ]

        self.assertEqual(
            posting_consistency_score(videos, as_of),
            100.0,
        )

    def test_engagement_slope_scores_upward_trend(self):
        as_of = timezone.localdate()
        snapshots = [
            SimpleNamespace(
                date=as_of - timedelta(days=2 - index),
                avg_engagement_rate=Decimal(str(value)),
            )
            for index, value in enumerate((3.0, 3.5, 4.0))
        ]

        self.assertEqual(
            engagement_trend_score(snapshots, as_of),
            55.0,
        )

    def test_follower_growth_compares_adjacent_weeks(self):
        as_of = timezone.localdate()
        snapshots = [
            SimpleNamespace(
                date=as_of - timedelta(days=14),
                follower_count=100,
            ),
            SimpleNamespace(
                date=as_of - timedelta(days=7),
                follower_count=105,
            ),
            SimpleNamespace(
                date=as_of,
                follower_count=112,
            ),
        ]

        score = follower_growth_score(snapshots, as_of)

        self.assertAlmostEqual(score, 66.6667, places=3)

    def test_activity_rewards_recent_frequent_posting(self):
        as_of = timezone.localdate()
        videos = [
            SimpleNamespace(
                posted_at=timezone.now()
                - timedelta(days=days_ago)
            )
            for days_ago in (0, 2, 4, 6)
        ]

        self.assertEqual(activity_score(videos, as_of), 100.0)

    def test_explanations_use_weighted_point_differences(self):
        previous = {
            "posting_consistency": 60,
            "engagement_trend": 50,
            "follower_growth": 50,
            "activity": 50,
        }
        current = {
            **previous,
            "posting_consistency": 80,
        }

        explanations = build_score_explanations(
            current,
            previous,
        )

        self.assertEqual(explanations[0]["points"], 5)
        self.assertEqual(
            explanations[0]["text"],
            "+5 points because posting consistency improved.",
        )


class CreatorScoreIntegrationTests(TestCase):
    def test_weighted_score_reads_video_and_snapshot_tables(self):
        account = TikTokAccount.objects.create(
            open_id="score-user",
            access_token="token",
        )
        as_of = timezone.localdate()

        for days_ago in (9, 6, 3, 0):
            TikTokVideo.objects.create(
                account=account,
                video_id=f"score-video-{days_ago}",
                posted_at=timezone.now()
                - timedelta(days=days_ago),
            )

        for days_ago, followers, engagement in (
            (14, 100, "3.0"),
            (7, 105, "3.5"),
            (0, 112, "4.0"),
        ):
            TikTokDailySnapshot.objects.create(
                account=account,
                date=as_of - timedelta(days=days_ago),
                follower_count=followers,
                avg_engagement_rate=Decimal(engagement),
            )

        result = get_creator_score(account, as_of)
        weighted_total = (
            0.25
            * result["components"]["posting_consistency"]
            + 0.30
            * result["components"]["engagement_trend"]
            + 0.25
            * result["components"]["follower_growth"]
            + 0.20
            * result["components"]["activity"]
        )

        self.assertEqual(result["score"], round(weighted_total))
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class BestPostingTimeTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="timing-user",
            access_token="token",
        )

    def create_video(
        self,
        video_id,
        posted_at,
        likes,
        comments,
        shares,
    ):
        return TikTokVideo.objects.create(
            account=self.account,
            video_id=video_id,
            posted_at=posted_at,
            like_count=likes,
            comment_count=comments,
            share_count=shares,
        )

    def test_groups_by_utc_weekday_and_hour_in_sql(self):
        monday_nine = datetime(
            2026,
            7,
            20,
            9,
            15,
            tzinfo=datetime_timezone.utc,
        )
        tuesday_ten = datetime(
            2026,
            7,
            21,
            10,
            30,
            tzinfo=datetime_timezone.utc,
        )
        self.create_video(
            "monday-1",
            monday_nine,
            likes=10,
            comments=3,
            shares=2,
        )
        self.create_video(
            "monday-2",
            monday_nine + timedelta(minutes=20),
            likes=20,
            comments=3,
            shares=2,
        )
        self.create_video(
            "tuesday-1",
            tuesday_ten,
            likes=80,
            comments=15,
            shares=5,
        )

        with self.assertNumQueries(1):
            result = get_best_posting_times(self.account)

        self.assertEqual(result["best"]["day_name"], "Tuesday")
        self.assertEqual(result["best"]["time_label"], "10:00 AM")
        self.assertEqual(
            result["best"]["avg_engagement"],
            100.0,
        )
        monday = result["recommendations"][1]
        self.assertEqual(monday["day_name"], "Monday")
        self.assertEqual(monday["sample_size"], 2)
        self.assertEqual(monday["avg_engagement"], 20.0)
        self.assertEqual(monday["confidence_score"], 40)

    def test_confidence_increases_with_sample_size(self):
        self.assertEqual(
            confidence_for_sample_size(1),
            {"score": 20, "label": "Low"},
        )
        self.assertEqual(
            confidence_for_sample_size(3),
            {"score": 60, "label": "Medium"},
        )
        self.assertEqual(
            confidence_for_sample_size(5),
            {"score": 100, "label": "High"},
        )

    def test_formats_midnight_and_afternoon(self):
        self.assertEqual(format_hour(0), "12:00 AM")
        self.assertEqual(format_hour(15), "3:00 PM")


class SyncTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="user-1",
            display_name="Creator",
            access_token="old-token",
            refresh_token="refresh-token",
            access_token_expires_at=timezone.now()
            - timedelta(minutes=1),
            refresh_token_expires_at=timezone.now()
            + timedelta(days=10),
        )

    @patch("tiktok_auth.sync.refresh_access_token")
    def test_refreshes_expiring_token_and_persists_rotation(self, refresh):
        refresh.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
            "scope": "video.list",
        }

        token = ensure_valid_access_token(self.account)

        self.assertEqual(token, "new-token")
        self.account.refresh_from_db()
        self.assertEqual(self.account.access_token, "new-token")
        self.assertEqual(
            self.account.refresh_token,
            "new-refresh-token",
        )

    @patch("tiktok_auth.sync.refresh_access_token")
    def test_does_not_refresh_token_with_more_than_buffer_left(
        self,
        refresh,
    ):
        self.account.access_token_expires_at = (
            timezone.now() + timedelta(hours=1)
        )
        self.account.save(update_fields=["access_token_expires_at"])

        token = ensure_valid_access_token(self.account)

        self.assertEqual(token, "old-token")
        refresh.assert_not_called()

    @patch("tiktok_auth.sync.get_all_tiktok_videos")
    @patch("tiktok_auth.sync.get_tiktok_profile")
    @patch("tiktok_auth.sync.ensure_valid_access_token")
    def test_sync_inserts_then_updates_video_and_extracts_hashtags(
        self,
        ensure_token,
        get_profile,
        get_videos,
    ):
        ensure_token.return_value = "valid-token"
        get_profile.return_value = {
            "display_name": "Updated Creator",
            "follower_count": 123,
            "video_count": 1,
        }
        get_videos.return_value = [
            {
                "id": "video-1",
                "video_description": "First post #Growth #Django",
                "create_time": 1_700_000_000,
                "view_count": 10,
                "like_count": 2,
            }
        ]

        first_result = sync_tiktok_performance(self.account)
        video = TikTokVideo.objects.get(video_id="video-1")

        self.assertEqual(first_result["videos_created"], 1)
        self.assertTrue(first_result["snapshot_created"])
        self.assertEqual(video.hashtags, ["growth", "django"])
        self.assertEqual(video.view_count, 10)
        snapshot = TikTokDailySnapshot.objects.get(
            account=self.account,
            date=timezone.localdate(),
        )
        self.assertEqual(
            snapshot.avg_engagement_rate,
            Decimal("20.0000"),
        )

        get_videos.return_value[0]["view_count"] = 25
        second_result = sync_tiktok_performance(self.account)
        video.refresh_from_db()
        snapshot.refresh_from_db()

        self.assertEqual(second_result["videos_updated"], 1)
        self.assertFalse(second_result["snapshot_created"])
        self.assertEqual(TikTokVideo.objects.count(), 1)
        self.assertEqual(TikTokDailySnapshot.objects.count(), 1)
        self.assertEqual(video.view_count, 25)
        self.assertEqual(
            snapshot.avg_engagement_rate,
            Decimal("8.0000"),
        )


class DailyGrowthTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="growth-user",
            access_token="token",
        )

    def test_diffs_today_against_yesterday(self):
        today = timezone.localdate()
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=today - timedelta(days=1),
            follower_count=100,
            likes_count=400,
            video_count=8,
            avg_engagement_rate=Decimal("4.2500"),
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=today,
            follower_count=163,
            likes_count=450,
            video_count=9,
            avg_engagement_rate=Decimal("5.0000"),
        )

        growth = get_daily_growth(self.account, today)

        self.assertTrue(growth["has_comparison"])
        self.assertEqual(growth["deltas"]["follower_count"], 63)
        self.assertEqual(
            growth["deltas"]["avg_engagement_rate"],
            Decimal("0.7500"),
        )

    def test_has_no_delta_without_yesterdays_snapshot(self):
        today = timezone.localdate()
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=today,
            follower_count=10,
        )

        growth = get_daily_growth(self.account, today)

        self.assertFalse(growth["has_comparison"])
        self.assertEqual(growth["deltas"], {})

    def test_dashboard_displays_signed_follower_delta(self):
        today = timezone.localdate()
        self.account.access_token_expires_at = (
            timezone.now() + timedelta(hours=1)
        )
        self.account.save(
            update_fields=["access_token_expires_at"]
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=today - timedelta(days=1),
            follower_count=100,
        )
        TikTokDailySnapshot.objects.create(
            account=self.account,
            date=today,
            follower_count=163,
        )
        session = self.client.session
        session["tiktok_account_id"] = self.account.pk
        session.save()

        response = self.client.get(
            reverse("tiktok-dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+63")


class DashboardPerformanceTests(TestCase):
    def test_analytics_exposes_top_bottom_topic_and_length(self):
        account = TikTokAccount.objects.create(
            open_id="performance-user",
            access_token="token",
        )
        for index, views in enumerate((500, 400, 300, 200, 100, 50)):
            TikTokVideo.objects.create(
                account=account,
                video_id=f"performance-{index}",
                title=f"Video {index}",
                hashtags=(
                    ["Transformation"]
                    if index < 3
                    else ["Tutorial"]
                ),
                duration=18 if index < 3 else 45,
                view_count=views,
                like_count=views // 10,
                posted_at=timezone.now()
                - timedelta(days=index),
            )

        analytics = get_account_analytics(account)

        expected_contract = {
            "top_videos",
            "lowest_videos",
            "average_views",
            "average_likes",
            "average_comments",
            "average_shares",
            "average_engagement_rate",
            "best_topic",
            "best_video_length",
            "best_posting_day",
            "best_posting_time",
            "follower_change",
            "engagement_change",
        }
        self.assertTrue(
            expected_contract.issubset(analytics)
        )
        self.assertEqual(len(analytics["top_videos"]), 5)
        self.assertEqual(len(analytics["lowest_videos"]), 5)
        self.assertEqual(
            analytics["best_topic"]["topic"],
            "transformation",
        )
        self.assertEqual(
            analytics["best_length"]["label"],
            "11–20 seconds",
        )


class PersonalizedIdeaGeneratorTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="generator-account",
            access_token="token",
            niche="hair styling",
        )

    def test_saves_personalized_ideas_and_avoids_duplicate_titles(self):
        analytics = {
            "videos_analyzed": 8,
            "average_views": 1000,
            "best_topic": {
                "topic": "transformation",
                "video_count": 5,
                "average_views": 2400,
                "confidence": "High confidence",
            },
            "best_video_length": {
                "label": "11–20 seconds",
                "video_count": 5,
            },
            "best_posting_day": {
                "day": "Friday",
                "video_count": 4,
            },
            "best_posting_time": {
                "time": "7 PM–9 PM",
                "video_count": 4,
            },
            "top_videos": [],
            "weak_topics": [{"topic": "product review"}],
            "last_three_topics": [
                "transformation",
                "transformation",
                "transformation",
            ],
            "summary": {
                "top_topic": "transformation",
                "best_length": "11–20 seconds",
                "best_day": "Friday",
                "best_time": "Evening",
            }
        }
        first = generate_personalized_content_ideas(
            self.account, analytics, count=5
        )
        second = generate_personalized_content_ideas(
            self.account, analytics, count=5
        )

        self.assertEqual(len(first), 5)
        self.assertEqual(len(second), 2)
        self.assertTrue(all(idea.is_generated for idea in first))
        self.assertEqual(first[0].suggested_posting_day, "Friday")
        self.assertEqual(first[0].suggested_duration, "11–20 seconds")
        self.assertIn("Based on 5 transformation videos", first[0].generation_reason)
        self.assertEqual(first[0].confidence, "High confidence")

    def test_balanced_score_does_not_overvalue_tiny_high_rate_video(self):
        large = TikTokVideo.objects.create(
            account=self.account,
            video_id="large",
            view_count=48000,
            like_count=5200,
            comment_count=310,
            share_count=490,
        )
        TikTokVideo.objects.create(
            account=self.account,
            video_id="tiny",
            view_count=50,
            like_count=10,
        )
        ranking = calculate_balanced_video_scores(
            list(self.account.videos.all())
        )
        self.assertEqual(ranking[0]["video"], large)

    def test_confidence_uses_evidence_count(self):
        self.assertEqual(confidence_for_evidence(1), "Limited data")
        self.assertEqual(confidence_for_evidence(3), "Medium confidence")
        self.assertEqual(confidence_for_evidence(5), "High confidence")


class ContentIdeaStatusViewTests(TestCase):
    def setUp(self):
        self.account = TikTokAccount.objects.create(
            open_id="status-account",
            access_token="token",
        )
        self.idea = ContentIdea.objects.create(
            account=self.account,
            title="My personal idea",
        )
        session = self.client.session
        session["tiktok_account_id"] = self.account.pk
        session.save()

    def test_status_action_updates_owned_idea(self):
        response = self.client.post(
            reverse(
                "update-content-idea-status",
                args=[self.idea.pk],
            ),
            {"status": ContentIdea.Status.FILMED},
        )
        self.assertRedirects(response, reverse("content-planner"))
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.status, ContentIdea.Status.FILMED)


class SyncCommandTests(TestCase):
    def setUp(self):
        TikTokAccount.objects.create(
            open_id="user-1",
            access_token="token",
        )
        TikTokAccount.objects.create(
            open_id="user-2",
            access_token="token",
        )

    @patch(
        "tiktok_auth.management.commands.sync_tiktok_videos."
        "sync_tiktok_performance"
    )
    def test_syncs_every_connected_account(self, sync):
        sync.return_value = {
            "videos_created": 1,
            "videos_updated": 2,
        }
        stdout = StringIO()

        call_command("sync_tiktok_videos", stdout=stdout)

        self.assertEqual(sync.call_count, 2)
        self.assertIn("2 video(s) created, 4 updated", stdout.getvalue())

    @patch(
        "tiktok_auth.management.commands.sync_tiktok_videos."
        "sync_tiktok_performance"
    )
    def test_continues_other_accounts_and_exits_nonzero_on_failure(
        self,
        sync,
    ):
        sync.side_effect = [
            RuntimeError("network error"),
            {"videos_created": 1, "videos_updated": 0},
        ]

        with self.assertRaises(CommandError):
            call_command(
                "sync_tiktok_videos",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(sync.call_count, 2)
