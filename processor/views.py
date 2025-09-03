from django.http import HttpResponse
from django.shortcuts import render
import io
from jobspy import scrape_jobs
import csv
import os
import pandas as pd
import datetime


def index(request):
    if request.method == "POST":
        # Capture form inputs
        job_roles_raw = request.POST.get("job_role", "").strip()
        job_roles = [role.strip() for role in job_roles_raw.split(",") if role.strip()]
        days = int(request.POST.get("days"))

        # Calculate hours_old from days
        hours_old = days * 24

        # Scrape jobs
        all_jobs = []

        for role in job_roles:
            jobs = scrape_jobs(
                site_name=["indeed", "linkedin", "google"],
                search_term=role,
                google_search_term=role,
                hours_old=hours_old,
            )
            jobs["search_term"] = role  # add a column to identify role
            all_jobs.append(jobs)

        # Merge into single DataFrame
        if all_jobs:
            jobs_df = pd.concat(all_jobs, ignore_index=True)
        else:
            jobs_df = pd.DataFrame()

        # Convert dataframe to CSV in memory
        csv_buffer = io.StringIO()
        jobs_df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\")
        csv_buffer.seek(0)

        # Return downloadable CSV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        response = HttpResponse(csv_buffer, content_type="text/csv")
        response['Content-Disposition'] = f'attachment; filename="jobs_{timestamp}.csv"'
        return response


    return render(request, "processor/index.html")
