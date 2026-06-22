from unittest.mock import patch

import pandas as pd
from django.test import TestCase


class IndexViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Search Filter")

    @patch("processor.views.scrape_jobs")
    def test_post_returns_csv_download(self, mock_scrape_jobs):
        mock_scrape_jobs.return_value = pd.DataFrame(
            [
                {
                    "title": "Senior Python Developer",
                    "company": "=FormulaTest",
                }
            ]
        )

        response = self.client.post(
            "/",
            {
                "job_role": '[{"value":"Python Developer"}]',
                "days": "7",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=\"jobs_", response["Content-Disposition"])
        self.assertContains(response, "search_term")
        self.assertContains(response, "Python Developer")
        self.assertContains(response, "'=FormulaTest")
        mock_scrape_jobs.assert_called_once()

    @patch("processor.views.scrape_jobs")
    def test_post_accepts_plain_comma_separated_roles(self, mock_scrape_jobs):
        mock_scrape_jobs.return_value = pd.DataFrame([{"title": "Data Analyst"}])

        response = self.client.post(
            "/",
            {
                "job_role": "Data Analyst, Data Scientist",
                "days": "14",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data Analyst")
        self.assertContains(response, "search_term")
        self.assertEqual(mock_scrape_jobs.call_count, 2)

    def test_post_rejects_invalid_days(self):
        response = self.client.post(
            "/",
            {
                "job_role": '[{"value":"Python Developer"}]',
                "days": "abc",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Days must be an integer.", status_code=400)

    @patch("processor.views.scrape_jobs")
    def test_post_returns_error_when_every_role_fails(self, mock_scrape_jobs):
        mock_scrape_jobs.side_effect = RuntimeError("boom")

        response = self.client.post(
            "/",
            {
                "job_role": '[{"value":"Python Developer"}]',
                "days": "7",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Unable to fetch jobs", status_code=404)
