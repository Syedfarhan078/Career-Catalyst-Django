import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.profiles.models import StudentProfile, StudentProject, StudentCertification
from apps.profiles.forms import StudentProfileForm, StudentProjectForm, StudentCertificationForm

User = get_user_model()

class StudentProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teststudent',
            email='student@test.com',
            password='testpassword123',
            first_name='Test',
            last_name='Student'
        )

    def test_profile_creation(self):
        profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            cgpa=9.15,
            graduation_year=2027,
            github='https://github.com/teststudent',
            linkedin='https://linkedin.com/in/teststudent'
        )
        self.assertEqual(profile.user.username, 'teststudent')
        self.assertEqual(float(profile.cgpa), 9.15)
        self.assertEqual(profile.calculate_completion_percentage(), 21) # 5 fields filled out of 23 checked fields

    def test_form_validation_phone_number_too_short(self):
        form_data = {
            'phone_number': '123',  # too short
            'cgpa': 9.0,
            'graduation_year': 2027
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_form_validation_cgpa_out_of_bounds(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 10.5,  # out of bounds (> 10)
            'graduation_year': 2027
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cgpa', form.errors)

    def test_form_validation_graduation_year_past(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2020  # in the past
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('graduation_year', form.errors)

    def test_form_validation_invalid_github_prefix(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2027,
            'github': 'https://gitlab.com/test'  # invalid prefix
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('github', form.errors)

    def test_form_validation_invalid_linkedin_prefix(self):
        form_data = {
            'phone_number': '12345678901',
            'cgpa': 8.5,
            'graduation_year': 2027,
            'linkedin': 'https://facebook.com/test'  # invalid prefix
        }
        form = StudentProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('linkedin', form.errors)


class UnifiedSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='settingstestuser',
            email='settings@test.com',
            password='InitialPassword123!',
            first_name='OriginalFirst',
            last_name='OriginalLast',
            bio='Original User Bio'
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            cgpa=8.5,
            graduation_year=2027,
            career_goal='Software Engineer',
            bio='Original Student Bio',
            github='https://github.com/studentdev',
            linkedin='https://linkedin.com/in/studentdev'
        )
        self.client.force_login(self.user)

    def test_settings_get_renders_with_tabs_and_forms(self):
        """Verify GET /profile/edit/ renders the unified Settings page with all 3 forms."""
        response = self.client.get('/profile/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/edit_profile.html')
        self.assertIn('account_form', response.context)
        self.assertIn('profile_form', response.context)
        self.assertIn('password_form', response.context)
        self.assertContains(response, 'Account Settings')
        self.assertContains(response, 'Career & Profile')
        self.assertContains(response, 'Security & Password')
        self.assertContains(response, 'Danger Zone')

    def test_settings_update_account_preserves_independent_fields(self):
        """Verify update_account updates User without overwriting StudentProfile duplicate fields."""
        post_data = {
            'action': 'update_account',
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast',
            'email': 'updated@test.com',
            'bio': 'New Account Level Bio',
            'github': 'https://github.com/userdev',
            'linkedin': 'https://linkedin.com/in/userdev'
        }
        response = self.client.post('/profile/edit/?tab=account', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=account')

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        # User fields updated
        self.assertEqual(self.user.first_name, 'UpdatedFirst')
        self.assertEqual(self.user.last_name, 'UpdatedLast')
        self.assertEqual(self.user.email, 'updated@test.com')
        self.assertEqual(self.user.bio, 'New Account Level Bio')

        # StudentProfile fields remain independent and untouched
        self.assertEqual(self.profile.bio, 'Original Student Bio')
        self.assertEqual(self.profile.github, 'https://github.com/studentdev')

    def test_settings_update_profile_preserves_independent_fields(self):
        """Verify update_profile updates StudentProfile without overwriting User duplicate fields."""
        post_data = {
            'action': 'update_profile',
            'phone_number': '9876543210',
            'cgpa': '9.25',
            'graduation_year': '2028',
            'career_goal': 'AI Research Engineer',
            'bio': 'New Student Career Summary',
            'github': 'https://github.com/updatedstudent',
            'linkedin': 'https://linkedin.com/in/updatedstudent'
        }
        response = self.client.post('/profile/edit/?tab=profile', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=profile')

        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        # StudentProfile fields updated
        self.assertEqual(self.profile.phone_number, '9876543210')
        self.assertEqual(float(self.profile.cgpa), 9.25)
        self.assertEqual(self.profile.bio, 'New Student Career Summary')
        self.assertEqual(self.profile.github, 'https://github.com/updatedstudent')

        # User bio remains independent and untouched
        self.assertEqual(self.user.bio, 'Original User Bio')

    def test_settings_change_password_success(self):
        """Verify change_password validates and updates password while preserving user session."""
        post_data = {
            'action': 'change_password',
            'old_password': 'InitialPassword123!',
            'new_password1': 'NewSecurePass2026!',
            'new_password2': 'NewSecurePass2026!'
        }
        response = self.client.post('/profile/edit/?tab=security', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=security')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass2026!'))

    def test_accounts_profile_redirects_to_settings(self):
        """Verify GET /accounts/profile/ seamlessly redirects to /profile/edit/?tab=account."""
        response = self.client.get('/accounts/profile/')
        self.assertRedirects(response, '/profile/edit/?tab=account')

    def test_profile_detail_view_renders(self):
        """Verify GET /profile/view/ renders the profile detail page in dash-shell."""
        response = self.client.get('/profile/view/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profiles/profile.html')
        self.assertContains(response, 'Student Profile')
        self.assertContains(response, 'Software Engineer')


class StudentPortfolioTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='portfoliostudent',
            email='portfolio@test.com',
            password='TestPassword123!',
            first_name='Portfolio',
            last_name='Student'
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            cgpa=8.8,
            graduation_year=2026,
            career_goal='Full Stack Engineer'
        )

        self.other_user = User.objects.create_user(
            username='otherstudent',
            email='other@test.com',
            password='OtherPassword123!'
        )
        self.other_profile = StudentProfile.objects.create(
            user=self.other_user,
            cgpa=7.5
        )

        self.client.force_login(self.user)

    def test_student_project_creation_and_ordering(self):
        p1 = StudentProject.objects.create(
            profile=self.profile,
            title='Alpha Project',
            technologies_used='Python, Django',
            description='First project',
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 2, 1)
        )
        p2 = StudentProject.objects.create(
            profile=self.profile,
            title='Beta Project',
            technologies_used='React, TypeScript',
            description='Second project',
            start_date=datetime.date(2025, 3, 1),
            end_date=datetime.date(2025, 5, 1)
        )
        self.assertIn('Alpha Project', str(p1))
        projects = list(self.profile.projects.all())
        # Ordered by -end_date, -created_at
        self.assertEqual(projects[0], p2)
        self.assertEqual(projects[1], p1)

    def test_student_project_chronological_date_validation(self):
        invalid_proj = StudentProject(
            profile=self.profile,
            title='Time Machine',
            start_date=datetime.date(2025, 5, 1),
            end_date=datetime.date(2025, 2, 1),
            is_current=False
        )
        with self.assertRaises(ValidationError):
            invalid_proj.clean()

    def test_student_certification_creation_and_fields(self):
        cert = StudentCertification.objects.create(
            profile=self.profile,
            name='AWS Certified Developer',
            organization='Amazon Web Services',
            issue_date=datetime.date(2025, 1, 15),
            expiration_date=datetime.date(2028, 1, 15),
            credential_id='AWS-DEV-9988',
            credential_url='https://aws.amazon.com/verify/9988'
        )
        self.assertEqual(str(cert), f"AWS Certified Developer - Amazon Web Services ({self.user.username})")

        invalid_cert = StudentCertification(
            profile=self.profile,
            name='Expired Before Issue',
            organization='Bad Academy',
            issue_date=datetime.date(2025, 6, 1),
            expiration_date=datetime.date(2025, 1, 1)
        )
        with self.assertRaises(ValidationError):
            invalid_cert.clean()

    def test_add_project_via_post_action(self):
        post_data = {
            'action': 'add_project',
            'title': 'AI Workflow Engine',
            'technologies_used': 'Python, Celery, Redis',
            'description': 'Distributed task pipeline',
            'github_url': 'https://github.com/portfoliostudent/ai-workflow',
            'live_demo_url': 'https://ai-workflow.example.com',
            'start_date': '2025-01-01',
            'is_current': 'on'
        }
        response = self.client.post('/profile/edit/?tab=portfolio', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=portfolio')

        project = self.profile.projects.filter(title='AI Workflow Engine').first()
        self.assertIsNotNone(project)
        self.assertEqual(project.technologies_used, 'Python, Celery, Redis')
        self.assertTrue(project.is_current)

    def test_add_certification_via_post_action(self):
        post_data = {
            'action': 'add_certification',
            'name': 'Google Cloud Associate Cloud Engineer',
            'organization': 'Google Cloud',
            'issue_date': '2025-02-01',
            'credential_id': 'GCP-ACE-12345',
            'credential_url': 'https://cloud.google.com/verify/12345',
            'skills_validated': 'Google Cloud, Kubernetes, Terraform'
        }
        response = self.client.post('/profile/edit/?tab=portfolio', data=post_data)
        self.assertRedirects(response, '/profile/edit/?tab=portfolio')

        cert = self.profile.certifications.filter(name='Google Cloud Associate Cloud Engineer').first()
        self.assertIsNotNone(cert)
        self.assertEqual(cert.organization, 'Google Cloud')
        self.assertEqual(cert.credential_id, 'GCP-ACE-12345')

    def test_delete_project_idor_prevention(self):
        # Project belonging to other_profile
        other_project = StudentProject.objects.create(
            profile=self.other_profile,
            title='Secret Other Project',
            technologies_used='Go, Rust'
        )

        response = self.client.post('/profile/edit/?tab=portfolio', data={
            'action': 'delete_project',
            'project_id': other_project.id
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(StudentProject.objects.filter(id=other_project.id).exists())

    def test_delete_certification_idor_prevention(self):
        # Certification belonging to other_profile
        other_cert = StudentCertification.objects.create(
            profile=self.other_profile,
            name='Other Certification',
            organization='Other Org'
        )

        response = self.client.post('/profile/edit/?tab=portfolio', data={
            'action': 'delete_certification',
            'certification_id': other_cert.id
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(StudentCertification.objects.filter(id=other_cert.id).exists())

    def test_public_profile_renders_portfolio_sections(self):
        StudentProject.objects.create(
            profile=self.profile,
            title='Showcase Project Alpha',
            technologies_used='Django, Vue.js',
            description='A showcase application.'
        )
        StudentCertification.objects.create(
            profile=self.profile,
            name='Showcase Cert Beta',
            organization='OpenAI'
        )

        response = self.client.get('/profile/view/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Showcase Project Alpha')
        self.assertContains(response, 'Django')
        self.assertContains(response, 'Vue.js')
        self.assertContains(response, 'Showcase Cert Beta')
        self.assertContains(response, 'OpenAI')

    def test_public_profile_and_edit_tab_render_roadmap_certificates(self):
        from apps.roadmaps.models import CareerPath, RoadmapCertificate
        path = CareerPath.objects.create(name='AI Engineer', slug='ai-engineer')
        cert = RoadmapCertificate.objects.create(
            certificate_id='CC-2026-PROFILETEST1',
            user=self.user,
            career_path=path,
            total_topics_completed=8,
            skills_summary='PyTorch, Transformers'
        )

        # Public Profile View
        res_view = self.client.get('/profile/view/')
        self.assertEqual(res_view.status_code, 200)
        self.assertContains(res_view, 'AI Engineer')
        self.assertContains(res_view, 'CC-2026-PROFILETEST1')
        self.assertContains(res_view, 'CareerCatalyst Verified')

        # Edit Profile Portfolio Tab
        res_edit = self.client.get('/profile/edit/?tab=portfolio')
        self.assertEqual(res_edit.status_code, 200)
        self.assertContains(res_edit, 'Verified Course Certificates')
        self.assertContains(res_edit, 'AI Engineer')
        self.assertContains(res_edit, 'CC-2026-PROFILETEST1')



