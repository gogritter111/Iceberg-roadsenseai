# RoadSense AI - Lambda Functions

AWS Lambda functions for the RoadSense AI system.

## Functions

### 1. roadsense-scraper
- **Trigger:** EventBridge (hourly)
- **Purpose:** Scrapes RSS feeds and weather data for Bangalore road incidents
- **Output:** Writes signals to DynamoDB

### 2. ingest-roadsense
- **Trigger:** DynamoDB Stream
- **Purpose:** Stores signal embeddings in ChromaDB and backs up to S3
- **Output:** ChromaDB vectors + S3 JSON files

### 3. roadsense-inference
- **Trigger:** EventBridge (every 5 minutes) + S3 events
- **Purpose:** Classifies signals, clusters by location/time, creates incidents
- **Output:** Writes incidents to DynamoDB

### 4. roadsense-classifier
- **Purpose:** Classification utilities for road-related signals

## Deployment

Each function directory contains the complete Lambda deployment package.

## Environment Variables

See individual function directories for required environment variables.
