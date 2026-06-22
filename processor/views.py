import csv
import datetime
import io
import json
import logging

import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from jobspy import scrape_jobs


logger = logging.getLogger(__name__)

_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")
_ALLOWED_DAYS = {7, 14, 30}


def _parse_job_roles(raw_job_role):
    if raw_job_role is None:
        return []

    raw_job_role = raw_job_role.strip()
    if not raw_job_role:
        return []

    try:
        parsed = json.loads(raw_job_role)
    except json.JSONDecodeError:
        parsed = [part.strip() for part in raw_job_role.split(",")]

    roles = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                value = item.get("value")
            else:
                value = item

            if value is None:
                continue

            value = str(value).strip()
            if value and value not in roles:
                roles.append(value)
    elif isinstance(parsed, str):
        value = parsed.strip()
        if value:
            roles.append(value)
    else:
        raise ValueError("Unsupported job role format.")

    return roles


def _parse_days(raw_days):
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        raise ValueError("Days must be an integer.")

    if days <= 0:
        raise ValueError("Days must be greater than zero.")

    if days not in _ALLOWED_DAYS:
        raise ValueError("Days must be one of 7, 14, or 30.")

    return days


def _coerce_dataframe(jobs, role):
    if jobs is None:
        return pd.DataFrame()

    if not isinstance(jobs, pd.DataFrame):
        jobs = pd.DataFrame(jobs)

    if jobs.empty:
        return jobs

    jobs = jobs.copy()
    jobs.insert(0, "search_term", role)

    for column in jobs.select_dtypes(include=["object"]).columns:
        jobs[column] = jobs[column].map(_sanitize_csv_value)

    return jobs


def _sanitize_csv_value(value):
    if pd.isna(value):
        return value

    if isinstance(value, str) and value.startswith(_CSV_DANGEROUS_PREFIXES):
        return "'" + value

    return value


def index(request):
    if request.method == "POST":
        job_role_raw = request.POST.get("job_role", "")
        try:
            job_roles = _parse_job_roles(job_role_raw)
            days = _parse_days(request.POST.get("days"))
        except ValueError as exc:
            return render(
                request,
                "processor/index.html",
                {"error_message": str(exc)},
                status=400,
            )

        if not job_roles:
            return render(
                request,
                "processor/index.html",
                {"error_message": "Please enter at least one job role."},
                status=400,
            )

        hours_old = days * 24
        all_jobs = []
        scrape_failures = []

        for role in job_roles:
            try:
                jobs = scrape_jobs(
                    site_name=["indeed", "linkedin", "google"],
                    search_term=role,
                    google_search_term=role,
                    hours_old=hours_old,
                    country_indeed='indonesia',
                )
                jobs_df = _coerce_dataframe(jobs, role)
            except Exception as exc:
                logger.exception("Job scrape failed for role=%s", role)
                scrape_failures.append(f"{role}: {exc}")
                continue

            if not jobs_df.empty:
                all_jobs.append(jobs_df)

        if not all_jobs:
            error_message = "No jobs were found for the requested roles."
            if scrape_failures:
                error_message = "Unable to fetch jobs for the requested roles."
            return render(
                request,
                "processor/index.html",
                {"error_message": error_message},
                status=404,
            )

        jobs_df = pd.concat(all_jobs, ignore_index=True, sort=False)
        csv_buffer = io.StringIO()
        jobs_df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
        response['Content-Disposition'] = f'attachment; filename="jobs_{timestamp}.csv"'
        return response


    return render(request, "processor/index.html")
