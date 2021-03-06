# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase
from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from django.contrib.auth.models import User
from .models import Profile, Mentor, Minor, Major, Course
from . import factories
from django.db import transaction
from django.core.exceptions import ValidationError

# Create your tests here.

class CreateUserTest(APITestCase):
    create_url = reverse('users:create')

    def tearDown(self):
        User.objects.all().delete()
        Profile.objects.all().delete()

    def test_create_user_has_profile_and_user(self):
        user_params = {
            'email': 'test@g.ucla.edu',
            'password': 'password',
        }

        resp = self.client.post(
            self.create_url,
            data=user_params,
        )

        user = User.objects.get(email=user_params['email'])
        profile = Profile.objects.get(user=user)

        self.assertEqual(user.email, user_params['email'])

    def test_user_username_and_email_equal(self):
        user_params = {
            'email': 'test2@g.ucla.edu',
            'password': 'password',
        }

        resp = self.client.post(
            self.create_url,
            data=user_params,
        )

        user = User.objects.get(email=user_params['email'])
        self.assertEqual(user.email, user.username)

    def test_create_user_cant_have_illegal_email(self):
        user_params = {
            'email': 'test@veryfakedomain.com@ucla.edu',
            'password': 'password',
        }

        resp = self.client.post(
            self.create_url,
            data=user_params,
        )

        self.assertFalse(User.objects.filter(email=user_params['email']).exists())

    def test_create_user_rejects_duplicate_emails(self):
        user_params = {
            'email': 'testCASE@g.ucla.edu',
            'password': 'password',
        }

        user_params_2 = {
            'email': 'testcase@g.ucla.edu',
            'password': 'password',
        }

        resp = self.client.post(
            self.create_url,
            data=user_params,
        )

        resp = self.client.post(
            self.create_url,
            data=user_params_2,
        )

        self.assertTrue(User.objects.filter(email=user_params['email']).exists())
        self.assertFalse(User.objects.filter(email=user_params_2['email']).exists())
        self.assertTrue(User.objects.filter(email__iexact=user_params_2['email']).exists())

class VerifyUserTest(APITestCase):
    verify_url = reverse('users:verify')

    def setUp(self):
        self.profile = factories.ProfileFactory()
        self.client.force_authenticate(user=self.profile.user)

    def tearDown(self):
        User.objects.all().delete()
        Profile.objects.all().delete()

    def test_verify_only_accepts_correct_code(self):
        user_params = {
            'verification_code' : 'fake_code_',
        }

        resp = self.client.post(
            self.verify_url,
            data=user_params,
        )

        self.assertEqual(resp.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verified, False)


    def test_verification_sets_verify_true(self):        
        user_params = {
            'verification_code' : self.profile.verification_code,
        }

        resp = self.client.post(
            self.verify_url,
            data=user_params,
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verified, True)

class ResetPasswordTest(APITestCase):
    reset_url = reverse('users:password_reset')

    def setUp(self):
        self.profile = factories.ProfileFactory()
        self.profile.password_reset_code = Profile.generate_password_reset_code()
        self.profile.save()

    def tearDown(self):
        User.objects.all().delete()
        Profile.objects.all().delete()

    def test_reset_changes_password(self):
        old_password = self.profile.user.password
        user_params = {
            'code' : self.profile.password_reset_code,
            'password' : 'new_'+old_password,
            'userid' : self.profile.user.id,
        }

        resp = self.client.post(
            self.reset_url,
            data=user_params,
        )

        self.assertEqual(self.profile.user.password, old_password)
        self.profile.user.refresh_from_db()
        self.assertNotEqual(self.profile.user.password, old_password)

    def test_reset_code_only_works_once(self):
        old_password = self.profile.user.password
        user_params = {
            'code' : self.profile.password_reset_code,
            'password' : 'new_'+old_password,
            'userid' : self.profile.user.id,
        }

        resp = self.client.post(
            self.reset_url,
            data=user_params,
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.password_reset_code, None)

class OwnProfileViewTest(APITestCase):
    own_profile_url = reverse('users:me')
    def setUp(self):
        self.profile = factories.ProfileFactory()
        self.client.force_authenticate(user=self.profile.user)

    def tearDown(self):
        User.objects.all().delete()
        Profile.objects.all().delete()

    def test_own_profile_returns_own_profile(self):
        resp = self.client.get(self.own_profile_url)
        self.assertEqual(self.profile.user.email, resp.data['email'])

    def test_edit_user_fields(self):
        data = {
            'first_name': 'fake',
            'last_name': 'name',
            'email': 'fakename@example.com',
        }
        resp = self.client.patch(self.own_profile_url, data=data)
        for field, val in data.items():
            self.assertEqual(val, resp.data[field])

    def test_phone_validation_accept(self):
        data = {
            'phone_number': '(012)345-6789',
        }
        resp = self.client.patch(self.own_profile_url, data=data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, resp.data['phone_number'])

    def test_phone_validation_deny(self):
        old_phone = self.profile.phone_number
        data = {
            'phone_number': '0123456789',
        }
        resp = self.client.patch(self.own_profile_url, data=data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, old_phone)

class MentorsSearchTest(APITestCase):
    mentors_search_url = reverse('users:mentors_search')
    def setUp(self):
        self.major = factories.MajorFactory(name='Test_Major0')
        self.mentor = factories.MentorFactory(major=[self.major])

        self.user1 = factories.UserFactory(first_name='Unique_First', last_name='Unique_Last')
        self.major1 = factories.MajorFactory(name='Test_Major1')
        self.minor1 = factories.MinorFactory(name='Unique_Minor')
        self.courses1 = factories.CourseFactory(name='Unique_Course')
        self.profile1 = factories.ProfileFactory(year=Profile.FRESHMAN, user=self.user1)
        self.mentor1 = factories.MentorFactory(major=[self.major1], minor=[self.minor1], 
                courses=[self.courses1], profile=self.profile1)

        self.user2 = factories.UserFactory(first_name='third', last_name='sample')
        self.major2 = factories.MajorFactory(name='Test_Major2')
        self.profile2 = factories.ProfileFactory(year=Profile.SOPHOMORE, user=self.user2)
        self.mentor2 = factories.MentorFactory(major=[self.major2], profile=self.profile2)

        self.major3 = factories.MajorFactory(name='Test_Major3')
        self.profile3 = factories.ProfileFactory(year=Profile.SOPHOMORE)
        self.mentor3 = factories.MentorFactory(major=[self.major3], profile=self.profile3)

        self.client.force_authenticate(user=self.mentor.profile.user)

    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()

    def test_filter_out_self(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': self.major.name,
            },
        )
        self.assertEqual(resp.data['count'], 3)

    def test_query_is_non_exact(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Major',
            },
        )
        self.assertEqual(resp.data['count'], 3)

    def test_query_is_case_insensitive(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'mAjOr',
            },
        )
        self.assertEqual(resp.data['count'], 3)

    def test_no_duplicates_in_queryset(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'unique',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile1.year)

    def test_query_checks_first_names(self):

        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Unique_First',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile1.year)
    
    def test_query_checks_last_names(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Unique_Last',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile1.year)
    
    def test_query_checks_majors(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Major',
            },
        )
        self.assertEqual(resp.data['count'], 3)

    def test_query_aliases_do_not_exclude_original_query(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'third',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile2.year)

    def test_query_aliasing_is_case_insensitive(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'tHiRd',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile2.year)

    def test_query_handles_spaces(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Test Major',
            },
        )
        self.assertEqual(resp.data['count'], 3)
        
    def test_filter_by_none(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
            },
        )
        self.assertEqual(resp.data['count'], 3)
        self.assertEqual(resp.data['results'][0]['profile']['year'], self.profile1.year)
        self.assertEqual(resp.data['results'][1]['profile']['year'], self.profile2.year)
        self.assertEqual(resp.data['results'][2]['profile']['year'], self.profile3.year)

    def test_random_with_query(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': self.major1.name,
                'random': 1,
            },
        )
        self.assertEqual(resp.data['count'], 1)
        

    def test_random_limits_queryset_size(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'query': 'Major',
                'random': 1,
            },
        )
        self.assertEqual(resp.data['count'], 1)
   
    def test_more_random_than_available(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'random': 100,
            },
        )
        self.assertEqual(resp.data['count'], 3)

    def test_random_with_no_args(self):
        resp = self.client.get(
            self.mentors_search_url,
            data={
                'random': '',
            },
        )
        self.assertEqual(resp.data['count'], 3)

class MentorsSearchWithFiltersTest(APITestCase):
    mentors_search_filter_url = reverse('users:mentors_search')
    def setUp(self):
        self.major = factories.MajorFactory(name='MATH')
        self.mentor = factories.MentorFactory(major=[self.major])

        self.user1 = factories.UserFactory(first_name='first_name_1', last_name='last_name_1')
        self.major1 = factories.MajorFactory(name='Jackpot')
        self.profile1 = factories.ProfileFactory(year=Profile.FRESHMAN, user=self.user1)
        self.mentor1 = factories.MentorFactory(major=[self.major1], profile=self.profile1)
        
        self.user2 = factories.UserFactory(first_name="Jackpot", last_name='last_name_2')
        self.major2 = factories.MajorFactory(name='major_sample_1')
        self.profile2 = factories.ProfileFactory(year=Profile.SOPHOMORE, user=self.user2)
        self.mentor2 = factories.MentorFactory(major=[self.major2], profile=self.profile2)

        self.user3 = factories.UserFactory(first_name='first_name_2', last_name='last_name_3')
        self.major3 = factories.MajorFactory(name='major_sample_2')
        self.profile3 = factories.ProfileFactory(year=Profile.SOPHOMORE, user=self.user3)
        self.mentor3 = factories.MentorFactory(major=[self.major3], profile=self.profile3, bio="Jackpot")

        self.user4 = factories.UserFactory(first_name='Sabbath', last_name='last_name_4')
        self.major4 = factories.MajorFactory(name='Sabbath')
        self.profile4 = factories.ProfileFactory(year=Profile.SOPHOMORE, user= self.user4)
        self.mentor4 = factories.MentorFactory(major=[self.major4], profile=self.profile4)

        self.user5 = factories.UserFactory(first_name='Baxxxx', last_name='last_name_5')
        self.major5 = factories.MajorFactory(name='major_sample_3')
        self.profile5 = factories.ProfileFactory(year=Profile.SOPHOMORE, user= self.user5)
        self.mentor5 = factories.MentorFactory(major=[self.major5], profile=self.profile5)

        self.user6 = factories.UserFactory(first_name='first_name_3', last_name='last_name_6')
        self.major6 = factories.MajorFactory(name='Banana')
        self.profile6 = factories.ProfileFactory(year=Profile.SOPHOMORE, user= self.user6)
        self.mentor6 = factories.MentorFactory(major=[self.major6], profile=self.profile6)

        self.user7 = factories.UserFactory(first_name='first_name_4', last_name='last_name_7')
        self.major7 = factories.MajorFactory(name='major_sample_4')
        self.profile7 = factories.ProfileFactory(year=Profile.SOPHOMORE, user= self.user7)
        self.mentor7 = factories.MentorFactory(major=[self.major7], profile=self.profile7, bio="Banaxx")

        self.user8 = factories.UserFactory(first_name='first_name_5', last_name='last_name_8')
        self.major8 = factories.MajorFactory(name='computer science')
        self.profile8 = factories.ProfileFactory(year=Profile.SENIOR, user=self.user8)
        self.mentor8 = factories.MentorFactory(major=[self.major8], profile=self.profile8)

        self.client.force_authenticate(user=self.mentor.profile.user)

    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()
        Profile.objects.all().delete()
    
    def test_major_filter(self):
        resp = self.client.get(
            self.mentors_search_filter_url,
            data={
                'query': 'Jackpot',
                'major': 'True',
            },
        )
        self.assertEqual(resp.data['count'],1)
        self.assertEqual(resp.data['results'][0]['profile']['id'], self.profile1.id)

    def test_name_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'Jackpot',
                'name': 'True',
            },
        )
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['profile']['id'], self.profile2.id)

    def test_bio_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'Jackpot',
                'bio':'True',
            },
        )
        self.assertEqual(resp.data['count'],1)
        self.assertEqual(resp.data['results'][0]['profile']['id'], self.profile3.id)

    def test_no_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'Jackpot',
            },
        )
        self.assertEqual(resp.data['count'],3)

    def test_all_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'Jackpot',
                'name':'True',
                'major':'True',
                'bio':'True',
            },
        )
        self.assertEqual(resp.data['count'],3)

    def test_no_duplicates_with_multiple_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'Sabbath',
                'name':'True',
                'major':'True',
            },
        )
        self.assertEqual(resp.data['count'],1)

    def test_sorting_with_multiple_filter(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'banana',
                'name':'True',
                'major':'True',
                'bio':'True',
            },
        )
        self.assertEqual(resp.data['count'],3)
        self.assertEqual(resp.data['results'][0]['profile']['id'], self.profile6.id)
        self.assertEqual(resp.data['results'][1]['profile']['id'], self.profile7.id)
        self.assertEqual(resp.data['results'][2]['profile']['id'], self.profile5.id)

    def test_dictionary_alias(self):
        resp=self.client.get(
            self.mentors_search_filter_url,
            data={
                'query':'cs',
                'major':'True',
            },
        )
        self.assertEqual(resp.data['count'],1)
        self.assertEqual(resp.data['results'][0]['profile']['id'], self.profile8.id)

class MentorsUpdateTest(APITestCase):
    mentors_update_url = reverse('users:mentors_me')
    def setUp(self):
        self.mentor = factories.MentorFactory()
        self.client.force_authenticate(user=self.mentor.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()

    def test_set_mentor_as_inactive(self):
        user_params = {
            'active' : False,
        }

        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
        )
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.active, False)
        
    def test_set_mentor_as_active(self):
        resp = self.client.post(
            self.mentors_update_url,
        )
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.active, True)

class CreateMentorTest(APITestCase):
    mentors_create_url = reverse('users:mentors_me')
    def setUp(self):
        self.profile = factories.ProfileFactory()
        self.client.force_authenticate(user=self.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()

    def test_create_mentor(self):
        self.assertEqual(Mentor.objects.filter(profile = self.profile).exists(), False)
        resp = self.client.post(
            self.mentors_create_url,
        )
        self.assertEqual(Mentor.objects.filter(profile = self.profile).exists(), True)

    def test_makes_existing_mentor_active(self):
        mentor = factories.MentorFactory(profile=self.profile, active=False)
        resp = self.client.post(
            self.mentors_create_url,
        )
        mentor.refresh_from_db()
        self.assertTrue(mentor.active)

class FindMentorByIDTest(APITestCase):
    def setUp(self):
        self.mentor = factories.MentorFactory()
        self.client.force_authenticate(user=self.mentor.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()

    def test_find_mentor_by_id(self):
        resp = self.client.get(
            reverse('users:mentor',kwargs={'mentor_id':self.mentor.id}),
        )
        self.assertEqual(resp.data['id'], self.mentor.id)

    def test_404_if_mentor_with_id_does_not_exist(self):
        resp = self.client.get(
            reverse('users:mentor',kwargs={'mentor_id': self.mentor.id + 100000000}), #100000000 is to force an invalid mentor ID
        )
        self.assertEqual(resp.status_code, 404)

class MajorEdittingTest(APITestCase):
    mentors_update_url = reverse('users:mentors_me')
    def setUp(self):
        self.mentor = factories.MentorFactory()
        self.client.force_authenticate(user=self.mentor.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()
        Major.objects.all().delete()

    def test_update_new_major(self):
        user_params = {
            'major': [
                { 'name' : 'Test_Major' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        major = self.mentor.major.all()
        self.assertEqual(len(major), 1)
        self.assertEqual(major[0].name, 'Test_Major')

    def test_update_removes_old_major(self):
        old_major = Major(name='Old Major')
        old_major.save()
        self.mentor.major.add(old_major)

        major = self.mentor.major.all()
        self.assertEqual(len(major), 1)
        self.assertEqual(major[0].name, old_major.name)

        user_params = {
            'major': [
                { 'name' : 'New_Major' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        major = self.mentor.major.all()
        self.assertEqual(len(major), 1)
        self.assertEqual(major[0].name, 'New_Major')

    def test_add_multiple_majors(self):
        user_params = {
            'major': [
                { 'name' : 'Test_Major' },
                { 'name' : 'Test_Major2' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        major = self.mentor.major.all()
        self.assertEqual(len(major), 2)
        self.assertEqual(major[0].name, 'Test_Major')
        self.assertEqual(major[1].name, 'Test_Major2')

    def test_limit_majors_to_two(self):
        user_params = {
            'major': [
                { 'name' : 'Test_Major' },
                { 'name' : 'Test_Major2' },
                { 'name' : 'Test_Major3' },
            ],
        }
        try:
            with transaction.atomic():
                resp = self.client.patch(
                    self.mentors_update_url,
                    data=user_params,
                    format='json',
                )
        except ValidationError as e:
            self.assertEquals('invalid', e.code)
        
class MinorEdittingTest(APITestCase):
    mentors_update_url = reverse('users:mentors_me')
    def setUp(self):
        self.mentor = factories.MentorFactory()
        self.client.force_authenticate(user=self.mentor.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()

    def test_update_new_minor(self):
        user_params = {
            'minor': [
                { 'name' : 'Test_Minor' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        minor = self.mentor.minor.all()
        self.assertEqual(len(minor), 1)
        self.assertEqual(minor[0].name, 'Test_Minor')

    def test_update_removes_old_minor(self):
        old_minor = Minor(name='Old Minor')
        old_minor.save()
        self.mentor.minor.add(old_minor)

        minor = self.mentor.minor.all()
        self.assertEqual(len(minor), 1)
        self.assertEqual(minor[0].name, old_minor.name)

        user_params = {
            'minor': [
                { 'name' : 'New_Minor' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        minor = self.mentor.minor.all()
        self.assertEqual(len(minor), 1)
        self.assertEqual(minor[0].name, 'New_Minor')

    def test_add_multiple_minors(self):
        user_params = {
            'minor': [
                { 'name' : 'Test_Minor' },
                { 'name' : 'Test_Minor2' },
                { 'name' : 'Test_Minor3' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        minor = self.mentor.minor.all()
        self.assertEqual(len(minor), 3)
        self.assertEqual(minor[0].name, 'Test_Minor')
        self.assertEqual(minor[1].name, 'Test_Minor2')
        self.assertEqual(minor[2].name, 'Test_Minor3')

    def test_limit_minors_to_three(self):
        user_params = {
            'minor': [
                { 'name' : 'Test_Minor' },
                { 'name' : 'Test_Minor2' },
                { 'name' : 'Test_Minor3' },
                { 'name' : 'Test_Minor4' },
            ],
        }
        try:
            with transaction.atomic():
                resp = self.client.patch(
                    self.mentors_update_url,
                    data=user_params,
                    format='json',
                )
        except ValidationError as e:
            self.assertEquals('invalid', e.code)

class CourseEdittingTest(APITestCase):
    mentors_update_url = reverse('users:mentors_me')
    def setUp(self):
        self.mentor = factories.MentorFactory()
        self.client.force_authenticate(user=self.mentor.profile.user)
    
    def tearDown(self):
        User.objects.all().delete()

    def test_update_new_course(self):
        user_params = {
            'courses': [
                { 'name' : 'New_Course' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        courses = self.mentor.courses.all()
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, 'New_Course')

    def test_update_removes_old_courses(self):
        old_course = Course(name='Old Course')
        old_course.save()
        self.mentor.courses.add(old_course)

        courses = self.mentor.courses.all()
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, old_course.name)

        user_params = {
            'courses': [
                { 'name' : 'New_Course' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        courses = self.mentor.courses.all()
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].name, 'New_Course')

    def test_add_multiple_courses(self):
        user_params = {
            'courses': [
                { 'name' : 'Test_Course' },
                { 'name' : 'Test_Course2' },
                { 'name' : 'Test_Course3' },
            ],
        }
        resp = self.client.patch(
            self.mentors_update_url,
            data=user_params,
            format='json',
        )
        self.mentor.refresh_from_db()
        courses = self.mentor.courses.all()
        self.assertEqual(len(courses), 3)
        self.assertEqual(courses[0].name, 'Test_Course')
        self.assertEqual(courses[1].name, 'Test_Course2')
        self.assertEqual(courses[2].name, 'Test_Course3')
