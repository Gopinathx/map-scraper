from django.db import models
from django.contrib.auth.models import User

class ScrapeAction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    keyword = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.keyword} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Business(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="businesses", null=True, blank=True)
    action = models.ForeignKey(ScrapeAction, on_delete=models.CASCADE, related_name="results", null=True)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

