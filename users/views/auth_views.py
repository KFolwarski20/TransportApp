from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from users.forms import RegisterForm, LoginForm


User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect("menu_glowne")  # 🔁 przekieruj, jeśli już zalogowany

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("menu_glowne")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("menu_glowne")  # 🔁 przekieruj, jeśli już zalogowany

    if request.method == "POST":
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("menu_glowne")
    else:
        form = LoginForm()
    return render(request, "users/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")
