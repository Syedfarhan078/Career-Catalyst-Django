from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='JobApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=200)),
                ('role_title', models.CharField(max_length=200)),
                ('job_type', models.CharField(choices=[('Full-Time', 'Full-Time'), ('Internship', 'Internship'), ('Contract', 'Contract'), ('Remote', 'Remote')], default='Full-Time', max_length=50)),
                ('status', models.CharField(choices=[('bookmarked', 'Bookmarked'), ('applied', 'Applied'), ('referral_requested', 'Referral Requested'), ('assessment', 'Online Assessment'), ('interview', 'Interviewing'), ('offer', 'Offer Received'), ('rejected', 'Rejected'), ('withdrawn', 'Withdrawn')], default='applied', max_length=30)),
                ('job_url', models.URLField(blank=True, help_text='Link to the original job posting', null=True)),
                ('location', models.CharField(blank=True, default='Remote / Flexible', max_length=150)),
                ('salary_or_stipend', models.CharField(blank=True, help_text='e.g. ₹8-12 LPA or ₹30,000/mo', max_length=100)),
                ('applied_date', models.DateField(default=django.utils.timezone.now)),
                ('interview_date', models.DateTimeField(blank=True, null=True)),
                ('last_contact_date', models.DateField(default=django.utils.timezone.now)),
                ('contact_person', models.CharField(blank=True, help_text='Recruiter or Referral contact name/email', max_length=150)),
                ('notes', models.TextField(blank=True, help_text='Interview rounds, take-home questions, or prep notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
