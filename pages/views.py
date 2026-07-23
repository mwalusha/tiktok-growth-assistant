from django.shortcuts import render
def home(request):
    return render(request, "pages/index.html")


def terms(request):
    return render(request, "pages/terms.html")


def privacy(request):
    return render(request, "pages/privacy.html")
