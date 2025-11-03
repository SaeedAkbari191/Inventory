from django.contrib.auth.models import AbstractUser
from django.db import models


# Create your models here.

class User(AbstractUser):
    role = models.CharField(max_length=30 ,verbose_name='Role')

    def __str__(self):
        return self.username

