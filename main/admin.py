from django.contrib import admin
from .models import Business, ScrapeAction

# This allows you to see and search Business data in the admin panel
@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'phone_number', 'created_at')
    search_fields = ('name', 'category')
    list_filter = ('category',)

@admin.register(ScrapeAction)
class ScrapeActionAdmin(admin.ModelAdmin):
    list_display = ('user','keyword','created_at')
