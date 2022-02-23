from . import skill_alexa as skill

from django.urls import include, path
from . import views
from django_ask_sdk.skill_adapter import SkillAdapter

view = SkillAdapter.as_view(skill=skill.sb.create())

urlpatterns = [
    path('skillCotriaje/', view, name="SkillCotriajeView")
]