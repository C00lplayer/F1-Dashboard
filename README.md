# 🏎️ F1 Dashboard – Formula 1 Power BI Analytics Project

An end-to-end **Power BI dashboard project** built around **Formula 1 race data**, delivering insights into **driver performance, constructor standings, qualifying trends, race outcomes, and season progression**.  
This project combines **Python-based data extraction**, **FastF1 data access**, and **Power BI storytelling** to create a professional F1 analytics experience for fans, analysts, and stakeholders.

<div align="center">
  <style>
    .f1-gallery {
      max-width: 1180px;
      margin: 18px auto 26px;
      text-align: center;
    }
    .f1-slider {
      position: relative;
      width: 100%;
      overflow: hidden;
      border-radius: 14px;
      background: #0b0b0d;
      border: 1px solid #2a2a2d;
      box-shadow: 0 10px 28px rgba(0,0,0,0.18);
    }
    .f1-slider input {
      display: none;
    }
    .f1-slides {
      display: flex;
      width: 300%;
      transition: transform 0.5s ease;
    }
    .f1-slide {
      width: 100%;
      flex-shrink: 0;
    }
    .f1-slide img {
      display: block;
      width: 100%;
      height: auto;
      border: 0;
      border-radius: 12px;
    }
    .f1-nav {
      display: flex;
      justify-content: center;
      gap: 10px;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .f1-nav label {
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #5a5a5d;
      cursor: pointer;
      transition: 0.2s ease;
    }
    .f1-nav label:hover {
      background: #9ea2a9;
    }
    #slide-1:checked ~ .f1-slider .f1-slides {
      transform: translateX(0%);
    }
    #slide-2:checked ~ .f1-slider .f1-slides {
      transform: translateX(-33.333%);
    }
    #slide-3:checked ~ .f1-slider .f1-slides {
      transform: translateX(-66.666%);
    }
    #slide-1:checked ~ .f1-slider .f1-nav label[for="slide-1"],
    #slide-2:checked ~ .f1-slider .f1-nav label[for="slide-2"],
    #slide-3:checked ~ .f1-slider .f1-nav label[for="slide-3"] {
      background: #e31c23;
      transform: scale(1.15);
    }
  </style>

  <div class="f1-gallery">
    <input type="radio" name="f1-slider" id="slide-1" checked>
    <input type="radio" name="f1-slider" id="slide-2">
    <input type="radio" name="f1-slider" id="slide-3">

    <div class="f1-slider">
      <div class="f1-slides">
        <div class="f1-slide">
          <img src="Dashboard_Pictures/Screenshot%202026-09-22%20112421.png" alt="F1 Dashboard Landing Page" />
        </div>
        <div class="f1-slide">
          <img src="Dashboard_Pictures/Screenshot%202026-09-22%20112445.png" alt="F1 Season Overview Dashboard" />
        </div>
        <div class="f1-slide">
          <img src="Dashboard_Pictures/Screenshot%202026-09-22%20112509.png" alt="F1 Past Race Details Dashboard" />
        </div>
      </div>

      <div class="f1-nav">
        <label for="slide-1" aria-label="Show landing page"></label>
        <label for="slide-2" aria-label="Show season overview"></label>
        <label for="slide-3" aria-label="Show past race details"></label>
      </div>
    </div>
  </div>
</div>

---

## Dashboard Overview

This dashboard is designed to help users explore the 2026 F1 season through a clean and interactive Power BI interface. It brings together multiple data points such as:

- Driver standings and championship progression
- Constructor performance across the season
- Race results and qualifying comparisons
- Position changes and fastest lap analysis
- Historical race summaries and upcoming race context

---

## Project Objective

Formula 1 is driven by performance, strategy, and consistency. Managing such a complex sport requires turning raw race data into insights that can answer key business and analytical questions such as:

- Who is leading the championship?
- Which team is dominating the season?
- How do qualifying positions compare with final race results?
- Which drivers are improving or slipping under pressure?
- How does a team’s cumulative performance evolve across the season?

This project transforms raw F1 data into an interactive, presentation-friendly dashboard that makes the race story easy to understand.

---


## Dataset Overview

The project uses a structured data pipeline built with **Python** and **FastF1** to pull live race session data and generate clean CSV files for Power BI. The dataset includes:

- Race schedules and event metadata
- Driver and constructor details
- Race results and qualifying results
- Sprint and race session outputs
- Standings and cumulative points tables
- Weather summaries and race conditions
- Fastest lap records
- Track and circuit-level metadata

The data is organized into a reusable analytics model that supports both **season review** and **past race analysis**.

---

## Dashboard Architecture

The dashboard is structured around a compact but effective analytical flow:

1. Landing Page
2. Season Overview
3. Past Race Details

Each page is designed to provide a different layer of insight, from a quick championship snapshot to a deeper dive into individual race results.

---

## Page-wise Explanation

---

### 1️⃣ Landing Page

**Purpose**
- Introduces the F1 dashboard experience
- Guides the user to the main dashboard views
- Creates a strong visual identity and portfolio-ready presentation

**Key Features**
- F1-inspired branding and dark theme
- Navigation cards for season overview and race analysis
- Clean, premium dashboard layout

---
<img src="Dashboard_Pictures/Screenshot%202026-09-22%20112421.png" alt="F1 Dashboard Landing Page" width="1000"/>

---

### 2️⃣ Season Overview Page

Provide a high-level snapshot of the championship battle across the current season.

**KPIs Displayed**
- Leading driver
- Leading constructor
- Race progress
- Driver standings table
- Constructor standings table
- Cumulative points trend
- Qualifying vs race position analysis

**Insights Provided**
- Who is leading the championship and by how much
- Which team is strongest across the season
- How points are accumulating over time
- Whether qualifying form translates into race performance
- Which drivers are trending upward or falling behind
- Helps fans and stakeholders understand the season narrative quickly
- Highlights momentum shifts and championship pressure
- Makes complex F1 performance trends easy to interpret

---
<img src="Dashboard_Pictures/Screenshot%202026-09-22%20112445.png" alt="F1 Season Overview Dashboard" width="1000"/>

---

### 3️⃣ Past Race Details Page

Offer a race-by-race breakdown with detailed performance insights for any selected Grand Prix.

**Key Features**
- Race selector on the left panel
- Race result table with finishing positions and lap times
- Qualifying results table
- Winner and fastest lap cards
- Position change chart

**Insights Provided**
- Final classification of the selected race
- Qualifying order comparison against race performance
- Fastest lap analysis
- Race progression and shifting positions
- Team/driver strategy impact at a single event level
- Allows decision-makers to review performance event by event
- Helps explain race outcomes beyond just final standings
- Supports deeper tactical and performance analysis for specific weekends

---
<img src="Dashboard_Pictures/Screenshot%202026-09-22%20112509.png" alt="F1 Past Race Details Dashboard" width="1000"/>

---

## Tools & Technologies Used

- **Microsoft Power BI**
- **Power BI Data Modeling**
- **DAX (Data Analysis Expressions)**
- **Python**
- **FastF1**
- **Pandas**
- **NumPy**
- **CSV-based data pipeline**
- **Data transformation and dashboard design**

---

## Data Pipeline Workflow

The project follows a structured data pipeline:

1. Pull F1 event schedule and session data using **FastF1**
2. Extract race, qualifying, standings, and weather-related datasets
3. Clean and transform the raw data using Python
4. Save processed files into the **powerbi_data** folder
5. Load them into Power BI and build interactive visuals
6. Design a polished dashboard optimized for analysis and presentation

This makes the project both reusable and scalable for additional seasons or future enhancements.

---

## Business Impact

This dashboard helps present F1 data in a way that is both engaging and analytical. It supports:

- Championship monitoring across the season
- Race-by-race performance review
- Team and driver benchmarking
- Qualifying-to-race trend analysis
- Quick insights for fans, analysts, and stakeholders

As a result, raw race data becomes a usable decision-support tool for understanding momentum, form, and competitive balance.

---


## Features to be Added

- Add more historical seasons for cross-year comparisons
- Add predictive race insights and win probability modeling
- Include track images with information on distance between finishers
- Expand into weather impact and circuit-specific analysis
- Integrate a full championship landing page with deeper storytelling views

---

## Repository Contents

- **Power BI dashboard file:** F1 Dashboard.pbix
- **Python extraction scripts:** data_extractor.py, quali.py
- **Processed data:** powerbi_data/
- **Cached session data:** fastf1_cache/
- **Dashboard visuals:** Dashboard_Pictures/

---

## Summary

The F1 Dashboard is a strong example of combining **sports data analytics, Power BI design, and Python automation** into one compelling portfolio project. It demonstrates how detailed race and qualifying data can be transformed into an insight-driven storytelling dashboard that feels professional, modern, and audience-friendly.

