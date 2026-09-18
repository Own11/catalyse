import json
from django.test import TestCase, Client
from django.urls import reverse
from profiles.models import UniversityProfile, Comment


class CommentTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.profile = UniversityProfile.objects.create(
            name="Казахский Национальный Университет",
            payload={
                "photos": {"campus": []},
                "socials": {},
                "ai_insights": {"summary": "Тестовое описание университета"},
                "campus_description": "Тестовое описание университета",
            },
        )


    def test_comment_model_default_author(self):
        comment = Comment.objects.create(
            profile=self.profile,
            text="Отличный университет с вековой историей!"
        )
        self.assertEqual(comment.author_name, "Аноним")
        self.assertEqual(str(comment), "Comment by Аноним on Казахский Национальный Университет")

    def test_comment_model_custom_author(self):
        comment = Comment.objects.create(
            profile=self.profile,
            author_name="Аскар",
            text="Прекрасный кампус."
        )
        self.assertEqual(comment.author_name, "Аскар")
        self.assertEqual(str(comment), "Comment by Аскар on Казахский Национальный Университет")

    def test_add_comment_api_success_json(self):
        url = reverse("profile-add-comment", kwargs={"profile_id": self.profile.id})
        response = self.client.post(
            url,
            data=json.dumps({"author_name": "Данияр", "text": "Учусь на 3 курсе, всё супер."}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["author_name"], "Данияр")
        self.assertEqual(data["text"], "Учусь на 3 курсе, всё супер.")
        self.assertEqual(data["profile_id"], self.profile.id)

        # Check DB count
        self.assertEqual(self.profile.comments.count(), 1)

    def test_add_comment_api_default_anonymous(self):
        url = reverse("profile-add-comment", kwargs={"profile_id": self.profile.id})
        response = self.client.post(
            url,
            data=json.dumps({"author_name": "   ", "text": "Анонимный отзыв о библиотеке."}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["author_name"], "Аноним")

    def test_add_comment_api_empty_text_error(self):
        url = reverse("profile-add-comment", kwargs={"profile_id": self.profile.id})
        response = self.client.post(
            url,
            data=json.dumps({"author_name": "Тест", "text": "   "}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_add_comment_api_nonexistent_profile(self):
        url = reverse("profile-add-comment", kwargs={"profile_id": 99999})
        response = self.client.post(
            url,
            data=json.dumps({"text": "Тестовый комментарий"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_profile_page_displays_comments(self):
        Comment.objects.create(
            profile=self.profile,
            author_name="Елена",
            text="Очень красивый спорткомплекс."
        )
        url = reverse("profile-page", kwargs={"profile_id": self.profile.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Отзывы и комментарии")
        self.assertContains(response, "Елена")
        self.assertContains(response, "Очень красивый спорткомплекс.")

    def test_landing_page_displays_recent_comments(self):
        Comment.objects.create(
            profile=self.profile,
            author_name="Алишер",
            text="Замечательное общежитие!"
        )
        url = reverse("landing")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Свежие отзывы")
        self.assertContains(response, "Алишер")
        self.assertContains(response, "Замечательное общежитие!")
        self.assertContains(response, "Казахский Национальный Университет")
