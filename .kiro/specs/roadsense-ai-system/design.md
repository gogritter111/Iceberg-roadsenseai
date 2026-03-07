# Design Document: RoadSense AI System

## Overview

RoadSense AI is a serverless, event-driven road infrastructure monitoring system built on AWS that automatically detects, validates, and reports road damage incidents across Indian cities. The system processes signals from multiple data sources through a 5-stage AI pipeline to generate high-confidence incident reports for municipal authorities.

### System Goals

- Automatically collect 5-10 signals per hour from RSS feeds and weather APIs
- Generate 200-400 validated incidents per month with 92% classification accuracy
- Maintain false positive rate below 8%
- Operate within $25-35 monthly cost budget
- Achieve 99.9% uptime with fully automated operation

### Key Capabilities

- Multi-source signal collection (8 RSS feeds + weather API)
- Multi-language translation (10 Indian languages → English)
- 5-stage AI pipeline for signal validation and clustering
- Semantic similarity-based correlation using vector embeddings
- Confidence scoring with source diversity weighting
- Human-readable incident explanations
- Automated data lifecycle management with TTL

### Technology Stack

- AWS Lambda (Python 3.12) for serverless compute
- Amazon Bedrock (Nova Micro, Nova Lite, Titan Embeddings V2) for AI processing
- DynamoDB for signal and incident storage with streams
- ChromaDB on EC2 for vector similarity search
- S3 for signal backup and static website hosting
- CloudFront for dashboard CDN
- EventBridge for scheduled triggers
- Secrets Manager for API key management
- Amazon Translate for multi-language support


## Architecture

### High-Level Architecture

The system follows an event-driven, serverless architecture with three main Lambda functions orchestrating a 5-stage AI pipeline:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RoadSense AI Pipeline                            │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ EventBridge  │────▶│   Scraper    │────▶│  DynamoDB    │
│  (Hourly)    │     │   Lambda     │     │   Signals    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                            │                     │
                            ▼                     │ Stream
                     ┌──────────────┐            │
                     │   Secrets    │            ▼
                     │   Manager    │     ┌──────────────┐
                     └──────────────┘     │    Ingest    │
                            │             │    Lambda    │
                            ▼             └──────┬───────┘
                     ┌──────────────┐            │
                     │   Translate  │            ├──────▶ ChromaDB (EC2)
                     │     API      │            │        Vector Store
                     └──────────────┘            │
                                                 ▼
┌──────────────┐                         ┌──────────────┐
│ RSS Feeds    │                         │      S3      │
│ (8 sources)  │                         │   Signals    │
└──────────────┘                         └──────┬───────┘
                                                 │ ObjectCreated
┌──────────────┐                                │
│ OpenWeather  │                                ▼
│     API      │                         ┌──────────────┐
└──────────────┘                         │  Inference   │
                                         │   Lambda     │
                                         └──────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │         5-Stage AI Pipeline (Amazon Bedrock)          │
                    ├───────────────────────────────────────────────────────┤
                    │  1. Normalizer    → Structure validation              │
                    │  2. Classification → Nova Micro (road-related?)       │
                    │  3. Intent        → Nova Micro (problem report?)      │
                    │  4. Correlation   → Titan Embeddings (clustering)     │
                    │  5. Inference     → Confidence scoring                │
                    │  6. Explanation   → Nova Lite (human summary)         │
                    └───────────────────────────────────────────────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  DynamoDB    │
                                         │  Incidents   │
                                         └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  CloudFront  │
                                         │  Dashboard   │
                                         └──────────────┘
```


### Data Flow

1. **Collection Phase** (Scraper Lambda)
   - EventBridge triggers hourly execution
   - Scrapes 8 RSS feeds (Google News targeted queries for Bangalore)
   - Fetches weather data from OpenWeatherMap API
   - Loads API keys from Secrets Manager
   - Translates non-English content to English via Amazon Translate
   - Deduplicates signals by SHA-256 hash of content + timestamp
   - Writes signals to DynamoDB with 30-day TTL

2. **Ingestion Phase** (Ingest Lambda)
   - DynamoDB Stream triggers on INSERT events
   - Generates 1024-dim embeddings via Titan Embeddings V2
   - Stores embeddings + metadata in ChromaDB
   - Writes enriched signals to S3 (triggers next phase)

3. **Inference Phase** (Inference Lambda)
   - S3 ObjectCreated event triggers processing
   - Normalizes signal structure
   - Runs 5-stage AI pipeline:
     - Classification: Road-related detection + damage type
     - Intent: Problem report vs noise/sarcasm filtering
     - Correlation: Geospatial + temporal + semantic clustering
     - Inference: Confidence scoring + severity assessment
     - Explanation: Human-readable incident summary
   - Writes incidents to DynamoDB

4. **Batch Processing** (Inference Lambda - Scheduled)
   - EventBridge triggers every 5 minutes
   - Loads all recent signals from DynamoDB
   - Re-clusters signals to update incidents with new information
   - Applies confidence decay to aging incidents

### Event-Driven Triggers

| Trigger | Target | Frequency | Purpose |
|---------|--------|-----------|---------|
| EventBridge Schedule | Scraper Lambda | Hourly | Signal collection |
| DynamoDB Stream | Ingest Lambda | Real-time | Embedding generation |
| S3 ObjectCreated | Inference Lambda | Real-time | Single signal processing |
| EventBridge Schedule | Inference Lambda | 5 minutes | Batch re-clustering |


## Components and Interfaces

### Scraper Lambda

**Purpose**: Collect signals from RSS feeds and weather APIs, translate non-English content, and write to DynamoDB.

**Trigger**: EventBridge hourly schedule

**Key Modules**:
- `lambda_function.py`: Orchestrates scraping, translation, and DynamoDB writes
- `rss_scraper.py`: Fetches from 8 Google News RSS feeds with Bangalore-specific queries
- `weather_scraper.py`: Fetches weather data from OpenWeatherMap API
- `translate.py`: Translates 10 Indian languages to English via Amazon Translate

**RSS Feed Configuration**:
```python
RSS_FEEDS = {
    "gnews_blr_pothole": "https://news.google.com/rss/search?q=bangalore+pothole",
    "gnews_blr_road_damage": "https://news.google.com/rss/search?q=bangalore+road+damage",
    "gnews_blr_waterlogging": "https://news.google.com/rss/search?q=bangalore+waterlogging",
    "gnews_blr_bbmp_road": "https://news.google.com/rss/search?q=bangalore+bbmp+road+repair",
    "gnews_blr_flooding": "https://news.google.com/rss/search?q=bangalore+road+flooding",
    "gnews_blr_sinkhole": "https://news.google.com/rss/search?q=bangalore+sinkhole+road",
    "gnews_blr_traffic": "https://news.google.com/rss/search?q=bangalore+road+blocked+accident",
    "gnews_blr_infrastructure": "https://news.google.com/rss/search?q=bengaluru+road+infrastructure+damage"
}
```

**Weather Configuration**:
- API: OpenWeatherMap (free tier, 1000 calls/day)
- Cities: Bangalore (lat: 12.9716, lon: 77.5946)
- Rain threshold: 2.5mm/hour (filters light drizzle)
- Flood weather IDs: 200-232, 300-302, 500-531, 611-616, 901-902

**Translation Support**:
- Languages: Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Malayalam, Gujarati, Punjabi, Urdu
- Service: Amazon Translate
- Stores both original_content and translated_content

**Signal ID Generation**:
```python
signal_id = SHA256(source + content + timestamp)[:32] → UUID format
```

**Deduplication Strategy**:
- Conditional DynamoDB put with `signal_id.not_exists()` check
- Prevents duplicate writes across hourly runs
- Returns counts: written, duplicates, failed

**Output Format**:
```json
{
  "signal_id": "uuid",
  "source": "news|weather",
  "source_name": "gnews_blr_pothole|openweathermap",
  "original_content": "text",
  "translated_content": "english text",
  "detected_language": "hi|en|...",
  "city": "Bangalore",
  "timestamp": "ISO8601",
  "scraped_at": "ISO8601",
  "location": {
    "coordinates": {"lat": 12.97, "lon": 77.59},
    "accuracy_meters": 500,
    "address": "MG Road, Bangalore"
  },
  "weather_data": {  // only for weather signals
    "condition": "heavy rain",
    "weather_id": 502,
    "rain_1h_mm": 18.5,
    "humidity": 92,
    "wind_speed": 12.3,
    "temp_c": 24.5
  },
  "ttl": 1234567890  // 30 days from now
}
```

**Error Handling**:
- Per-source error isolation (one feed failure doesn't block others)
- Secrets Manager fallback to environment variables
- Logs errors with `exc_info=True` for debugging
- Returns summary with success/failure counts

**Performance**:
- Target: 30 seconds average execution time
- Expected output: 5-10 signals per hour
- Cost optimization: Pre-filters Mumbai signals, weather signals bypass AI classification


### Ingest Lambda

**Purpose**: Generate vector embeddings and store signals in ChromaDB for semantic similarity search.

**Trigger**: DynamoDB Stream on roadsense-signals table (NEW_IMAGE events only)

**Key Operations**:
1. Parse DynamoDB Stream records (TypeDeserializer for DynamoDB format)
2. Validate signal structure (signal_id + translated_content required)
3. Generate 1024-dim embedding via Titan Embeddings V2
4. Store embedding + metadata in ChromaDB
5. Write enriched signal to S3 (triggers Inference Lambda)

**Embedding Configuration**:
- Model: `amazon.titan-embed-text-v2:0`
- Dimension: 1024 (validated before storage)
- Input: translated_content field
- Bedrock region: us-east-1

**ChromaDB Integration**:
- Host: EC2 instance at 98.80.183.42:8000
- API: HTTP REST API (v2)
- Collection ID: 9c0d4b37-ec84-4e00-bf45-018feced81d6
- Endpoint: `/api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/add`

**ChromaDB Metadata Schema**:
```python
{
  "signal_type": "news|weather",
  "original_content": "text",
  "detected_language": "hi|en|...",
  "source": "news|weather",
  "source_name": "gnews_blr_pothole|openweathermap",
  "timestamp": "ISO8601",
  "city": "Bangalore",
  "latitude": 12.97,
  "longitude": 77.59,
  "accuracy_meters": 500,
  "address": "MG Road, Bangalore"
}
```

**S3 Write Configuration**:
- Bucket: roadsense-raw-signals-778277577994
- Key format: `signals/{signal_id}.json`
- ContentType: application/json
- Adds `ingested_at` timestamp
- Parses JSON string fields back to dict objects

**Batch Processing**:
- Processes DynamoDB Stream batches independently
- One signal failure doesn't block others
- Always returns HTTP 200 to prevent Lambda retry of entire batch
- Returns individual signal results with status

**Error Handling**:
- ChromaDB heartbeat check before processing
- Validation errors: Log warning, return failed status
- Embedding errors: Log error, return failed status
- ChromaDB errors: Raise RuntimeError with connection details
- Never raises exceptions that would trigger Lambda retry

**Performance**:
- Target: 5 seconds per signal
- Embedding generation: ~1-2 seconds
- ChromaDB write: ~500ms
- S3 write: ~200ms


### Inference Lambda

**Purpose**: Orchestrate 5-stage AI pipeline to validate signals and generate incidents.

**Triggers**:
1. S3 ObjectCreated event (real-time single signal processing)
2. EventBridge schedule (batch re-clustering every 5 minutes)

**Execution Modes**:

**Mode 1: Real-Time Processing** (S3 trigger)
1. Read new signal from S3
2. Normalize signal structure
3. Run Classification Agent (Nova Micro)
4. Run Intent Agent (Nova Micro)
5. Save signal to DynamoDB
6. Load all recent signals from DynamoDB (limit 100)
7. Run Correlation Agent (cluster all signals)
8. Run Inference Agent (score clusters)
9. Run Explanation Agent (Nova Lite)
10. Save incidents to DynamoDB

**Mode 2: Batch Processing** (EventBridge trigger)
1. Load all signals from DynamoDB (limit 100)
2. Parse JSON string fields (location, classification, intent)
3. Classify signals missing classification/intent
4. Update signals in DynamoDB
5. Run Correlation Agent (cluster all signals)
6. Run Inference Agent (score clusters)
7. Run Explanation Agent (Nova Lite)
8. Save incidents to DynamoDB

**Agent Pipeline**:

```
Signal → Normalizer → Classification → Intent → [DynamoDB Save]
                                                      ↓
                                              Load All Signals
                                                      ↓
                                                Correlation
                                                      ↓
                                                 Inference
                                                      ↓
                                                Explanation
                                                      ↓
                                            [DynamoDB Save]
```

**DynamoDB Operations**:
- Signals table: Batch writer for updates
- Incidents table: Batch writer for inserts
- JSON serialization: location, classification, intent, confidence_history
- Decimal conversion: Convert Decimal to float/int before JSON serialization
- Field filtering: Remove empty strings and None values

**Error Handling**:
- S3 read: Try-except with HTTP 500 on failure
- DynamoDB operations: Try-except with logging
- Agent failures: Logged but don't block pipeline
- Returns HTTP 200 for scheduled runs even with 0 incidents

**Performance**:
- Target: 60 seconds for single signal processing
- Batch mode: Processes up to 100 signals
- Agent execution: ~5-10 seconds per stage
- DynamoDB batch writes: ~1-2 seconds

**Output Format**:
```json
{
  "statusCode": 200,
  "signals_processed": 5,
  "clusters_formed": 2,
  "incidents_created": 1,
  "incident_ids": ["uuid1"]
}
```


### AI Agent Designs

#### 1. Normalizer

**Purpose**: Ensure consistent signal structure before AI processing.

**Operations**:
- Validate location field structure (coordinates, accuracy_meters, address)
- Parse JSON string fields back to dict objects
- Convert flat latitude/longitude to nested coordinates format
- Set default values for missing optional fields
- Validate required fields: signal_id, translated_content

**Location Normalization**:
```python
# Input (dataset format)
{"latitude": 12.97, "longitude": 77.60, "accuracy_meters": 56, "address": "MG Road"}

# Output (pipeline format)
{"coordinates": {"lat": 12.97, "lon": 77.60}, "accuracy_meters": 56, "address": "MG Road"}
```

#### 2. Classification Agent

**Purpose**: Determine if signal describes road infrastructure problem and identify damage type.

**Model**: Amazon Nova Micro (`amazon.nova-micro-v1:0`)

**Input**: translated_content (English text)

**Output**:
```json
{
  "is_road_related": true,
  "damage_type": "pothole|surface_wear|flooding|general|null",
  "confidence": 0.92,
  "reasoning": "Post clearly describes a large pothole causing vehicle damage"
}
```

**Damage Type Classification**:
- `pothole`: Mentions potholes, craters, holes, gaddha, khada
- `surface_wear`: Mentions cracks, worn surface, broken asphalt, uneven road
- `flooding`: Mentions waterlogging, road underwater, flood on road
- `general`: Road-related but doesn't fit specific categories
- `null`: Not road-related

**Pre-Classification Optimizations** (cost savings):
1. Weather signals: Pre-classify as road-related, damage_type=flooding, confidence=0.75
2. Mumbai signals: Pre-classify as not road-related, confidence=0.0 (filtered by address)

**Confidence Range**: 0.01 to 0.99 (never exactly 0.0 or 1.0)

**Fallback Logic**: If model response parsing fails, return is_road_related=false, confidence=0.1

**Target Accuracy**: 92% or higher

#### 3. Intent Agent

**Purpose**: Filter noise, sarcasm, and speculation from road-related signals.

**Model**: Amazon Nova Micro (`amazon.nova-micro-v1:0`)

**Input**: Signal with classification result

**Output**:
```json
{
  "is_problem_report": true,
  "urgency_level": "low|medium|high|critical",
  "context_type": "direct_report|indirect_mention|news_article|weather_alert|speculation|sarcasm|ambiguous",
  "confidence_modifier": 0.1,
  "reasoning": "First-hand account with specific location detail"
}
```

**Urgency Levels**:
- `critical`: Immediate danger, accident, road completely blocked
- `high`: Significant damage, vehicle damage reported
- `medium`: Noticeable damage, inconvenience
- `low`: Minor issue, old report, vague mention

**Context Types**:
- `direct_report`: First-hand account of seeing/experiencing problem
- `indirect_mention`: Heard from someone else, general area mention
- `news_article`: Formal news report
- `weather_alert`: Weather-based road risk signal
- `speculation`: Guessing or predicting a problem might exist
- `sarcasm`: Sarcastic complaint
- `ambiguous`: Unclear intent

**Confidence Modifier Range**: -0.4 to +0.2
- Boost (+0.1 to +0.2): Direct first-hand report with location specifics
- Neutral (0.0): Clear report but no location or vague details
- Reduce (-0.1 to -0.2): Indirect mention, speculation, ambiguous
- Reduce (-0.3 to -0.4): Clear sarcasm, clear non-report

**Pre-Classification Optimizations**:
1. Weather signals: Pre-classify as problem report, urgency=medium, context=weather_alert
2. News signals: Classify context_type as news_article

**Confidence Adjustment**: Applies modifier to classification confidence score in-place

**Fallback Logic**: If model response parsing fails, return is_problem_report=true, confidence_modifier=0.0


#### 4. Correlation Agent

**Purpose**: Cluster signals by geographic proximity, temporal relation, and semantic similarity.

**Model**: Amazon Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`)

**Clustering Parameters**:
- Geographic radius: 500 meters (Haversine distance)
- Time window: 7 days (sliding window)
- Semantic similarity threshold: 0.75 (cosine similarity)
- Minimum cluster size: 1 signal

**Eligibility Filtering**:
- Include signals where: `is_road_related=true AND is_problem_report=true`
- Always include weather signals regardless of is_problem_report

**Clustering Algorithm**: Union-Find
1. Compare every pair of eligible signals
2. Check temporal relation (within 7 days)
3. Check geographic relation (within 500m OR same city)
4. Check semantic similarity (cosine similarity ≥ 0.75)
5. Union signals that meet all three criteria
6. Group signals by cluster root
7. Discard clusters below minimum size

**Geographic Matching**:
- Primary: Haversine distance between coordinates
- Fallback: City-level matching if coordinates missing
- Centroid calculation: Average of all signal coordinates

**Semantic Similarity**:
- Fetch embeddings from ChromaDB or generate via Titan
- Compute cosine similarity between embedding vectors
- Assume similar if embeddings unavailable (avoid false negatives)

**Cluster ID Generation**:
```python
cluster_id = SHA256(sorted(signal_ids).join(":"))[:32] → UUID format
```

**Cluster Output**:
```json
{
  "cluster_id": "uuid",
  "signal_ids": ["uuid1", "uuid2", "uuid3"],
  "signal_count": 3,
  "signals": [...],
  "location": {
    "center_coordinates": {"lat": 12.97, "lon": 77.59},
    "radius_meters": 500,
    "address": "MG Road, Bangalore"
  },
  "damage_type": "pothole",
  "source_diversity": ["reddit", "youtube", "times_of_india"],
  "source_count": 3,
  "earliest_signal": "ISO8601",
  "latest_signal": "ISO8601",
  "created_at": "ISO8601"
}
```

**Primary Damage Type**: Most common damage_type among cluster signals

**Source Diversity**: Unique source_name values (important for confidence scoring)


#### 5. Inference Agent

**Purpose**: Compute confidence scores and severity levels for incident clusters.

**Confidence Scoring Algorithm** (0-100 scale):

| Component | Max Points | Calculation |
|-----------|------------|-------------|
| Source Diversity | 30 | Weighted by source type + bonus for 3+ sources |
| Signal Count | 20 | Scaled by count (1=2pts, 2=4pts, 3=8pts, 5=12pts, 7=16pts, 10+=20pts) |
| Urgency Levels | 20 | Weighted by highest urgency (critical=20, high=14, medium=8, low=3) |
| Classification Confidence | 20 | Average confidence × 20 |
| Recency | 10 | Full points for <24h, decaying to 1pt for >120h |
| Weather Correlation | 10 | Bonus if cluster contains weather signal |
| **Total** | **110** | **Clamped to 100** |

**Source Diversity Weights**:
```python
{
  "times_of_india": 18,
  "ndtv": 18,
  "the_hindu": 18,
  "deccan_herald": 16,
  "hindustan_times": 16,
  "reddit": 15,
  "youtube": 12,
  "openweathermap": 10,
  "unknown": 5
}
```

**Source Diversity Bonuses**:
- 3+ distinct sources: +10 points
- 2 distinct sources: +5 points

**Urgency Weights**:
```python
{
  "critical": 20,
  "high": 14,
  "medium": 8,
  "low": 3
}
```

**Recency Scoring**:
- ≤24 hours: 10 points
- ≤48 hours: 7 points
- ≤72 hours: 5 points
- ≤120 hours: 3 points
- >120 hours: 1 point

**Severity Level Determination**:
- `critical`: confidence ≥ 85 OR any signal has critical urgency
- `high`: confidence ≥ 65 OR any signal has high urgency
- `medium`: confidence ≥ 45
- `low`: confidence < 45

**Incident Creation Threshold**: confidence_score > 30

**Incident Archive Threshold**: confidence_score ≤ 30

**Confidence Decay** (for aging incidents):
- No decay for first 3 days
- Lose ~5 points per day after 3 days with no new signals
- Status changes: active → monitoring → archived

**Incident Output**:
```json
{
  "incident_id": "uuid",
  "cluster_id": "uuid",
  "signal_ids": ["uuid1", "uuid2"],
  "signal_count": 2,
  "location": {...},
  "damage_type": "pothole",
  "confidence_score": 82,
  "severity_level": "high",
  "status": "active",
  "source_diversity": ["reddit", "times_of_india"],
  "explanation": null,
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "confidence_history": [
    {
      "timestamp": "ISO8601",
      "confidence_score": 82,
      "reason": "initial_scoring"
    }
  ]
}
```


#### 6. Explanation Agent

**Purpose**: Generate human-readable summaries of incidents for municipal authorities.

**Model**: Amazon Nova Lite (`amazon.nova-lite-v1:0`)

**Input**: Incident with embedded signals

**Output**: 2-4 sentence explanation (max 600 characters)

**Explanation Requirements**:
- Mention number and types of sources (e.g., "3 Reddit posts and 1 news article")
- Reference original languages if signals were translated (e.g., "originally in Hindi and Telugu")
- Include location and damage type
- Write in plain English for non-technical audience
- No bullet points, no technical terms, no confidence scores
- Factual and neutral tone

**Example Explanation**:
```
Multiple reports of severe waterlogging on NH-65 in Hyderabad were detected across 
3 Reddit posts (originally in Hindi and Telugu) and 1 Times of India article over 
2 days, coinciding with heavy rainfall recorded by weather monitoring. The reports 
describe vehicles getting stranded and road surface damage consistent with flooding.
```

**Language Display Names**:
```python
{
  "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada",
  "bn": "Bengali", "mr": "Marathi", "ml": "Malayalam", "gu": "Gujarati",
  "pa": "Punjabi", "ur": "Urdu", "en": "English"
}
```

**Source Display Names**:
```python
{
  "reddit": "Reddit",
  "youtube": "YouTube",
  "times_of_india": "Times of India",
  "ndtv": "NDTV",
  "the_hindu": "The Hindu",
  "deccan_herald": "Deccan Herald",
  "hindustan_times": "Hindustan Times",
  "openweathermap": "weather data"
}
```

**Fallback Explanation** (if AI model fails):
```
{signal_count} signals indicating {damage_type} in {location} were detected 
across {sources}. The incident has been classified as {severity} severity 
and requires review by the relevant municipal authority.
```

**Prompt Engineering**:
- Includes sample signals (up to 8) with source, language, urgency, and content
- Specifies time range of signals
- Provides example good explanation
- Emphasizes plain language and flowing prose


## Data Models

### DynamoDB Signals Table

**Table Name**: roadsense-signals

**Partition Key**: signal_id (String)

**Attributes**:
```python
{
  "signal_id": "uuid",                    # Partition key
  "source": "news|weather",               # Signal source type
  "source_name": "gnews_blr_pothole|...", # Specific source identifier
  "original_content": "text",             # Original text (any language)
  "translated_content": "english text",   # English translation
  "detected_language": "hi|en|...",       # ISO 639-1 language code
  "city": "Bangalore",                    # City name
  "timestamp": "ISO8601",                 # Signal creation time
  "scraped_at": "ISO8601",                # Scraper execution time
  "ingested_at": "ISO8601",               # Ingest Lambda execution time
  "saved_at": "ISO8601",                  # Inference Lambda save time
  "location": "JSON string",              # Serialized location object
  "weather_data": "JSON string",          # Serialized weather data (optional)
  "classification": "JSON string",        # Serialized classification result
  "intent": "JSON string",                # Serialized intent result
  "ttl": 1234567890                       # Unix timestamp (30 days from scraped_at)
}
```

**Location Object Structure** (stored as JSON string):
```json
{
  "coordinates": {
    "lat": 12.9716,
    "lon": 77.5946
  },
  "accuracy_meters": 500,
  "address": "MG Road, Bangalore"
}
```

**Classification Object Structure** (stored as JSON string):
```json
{
  "is_road_related": true,
  "damage_type": "pothole",
  "confidence": 0.92,
  "reasoning": "Post clearly describes a large pothole"
}
```

**Intent Object Structure** (stored as JSON string):
```json
{
  "is_problem_report": true,
  "urgency_level": "high",
  "context_type": "direct_report",
  "confidence_modifier": 0.1,
  "reasoning": "First-hand account with specific location"
}
```

**DynamoDB Streams Configuration**:
- Stream view type: NEW_IMAGE
- Triggers: Ingest Lambda on INSERT events
- Batch size: Default (100 records)

**TTL Configuration**:
- Attribute: ttl
- Expiration: 30 days from scraped_at
- Automatic cleanup: DynamoDB deletes expired items

**Indexes**: None (partition key only)

**Capacity Mode**: On-demand (pay per request)


### DynamoDB Incidents Table

**Table Name**: roadsense-incidents

**Partition Key**: incident_id (String)

**Attributes**:
```python
{
  "incident_id": "uuid",                  # Partition key (same as cluster_id)
  "cluster_id": "uuid",                   # Cluster identifier
  "signal_ids": ["uuid1", "uuid2"],       # List of signal IDs in cluster
  "signal_count": 3,                      # Number of signals
  "damage_type": "pothole",               # Primary damage type
  "severity_level": "high",               # low|medium|high|critical
  "confidence_score": 82,                 # 0-100 score
  "status": "active",                     # active|monitoring|archived
  "explanation": "text",                  # Human-readable summary
  "source_diversity": ["reddit", "..."],  # List of unique sources
  "location": "JSON string",              # Serialized location object
  "confidence_history": "JSON string",    # Serialized confidence history
  "created_at": "ISO8601",                # Incident creation time
  "updated_at": "ISO8601"                 # Last update time
}
```

**Location Object Structure** (stored as JSON string):
```json
{
  "center_coordinates": {
    "lat": 12.9716,
    "lon": 77.5946
  },
  "radius_meters": 500,
  "address": "MG Road, Bangalore"
}
```

**Confidence History Structure** (stored as JSON string):
```json
[
  {
    "timestamp": "ISO8601",
    "confidence_score": 82,
    "reason": "initial_scoring"
  },
  {
    "timestamp": "ISO8601",
    "confidence_score": 75,
    "reason": "temporal_decay"
  }
]
```

**Status Values**:
- `active`: Confidence > 30, incident is current
- `monitoring`: Confidence 30-45, incident is aging
- `archived`: Confidence ≤ 30, incident is old or resolved

**Indexes**: None (partition key only)

**Capacity Mode**: On-demand (pay per request)

**No TTL**: Incidents are permanent records for audit trail


### ChromaDB Collection

**Host**: EC2 instance at 98.80.183.42:8000

**Collection ID**: 9c0d4b37-ec84-4e00-bf45-018feced81d6

**Tenant**: default_tenant

**Database**: default_database

**Document Structure**:
```python
{
  "id": "signal_id (uuid)",
  "document": "translated_content (text)",
  "embedding": [1024-dim float vector],
  "metadata": {
    "signal_type": "news|weather",
    "original_content": "text",
    "detected_language": "hi|en|...",
    "source": "news|weather",
    "source_name": "gnews_blr_pothole|...",
    "timestamp": "ISO8601",
    "city": "Bangalore",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "accuracy_meters": 500,
    "address": "MG Road, Bangalore"
  }
}
```

**API Endpoints**:
- Add: `POST /api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/add`
- Query: `POST /api/v2/tenants/{tenant}/databases/{database}/collections/{collection_id}/query`
- Heartbeat: `GET /api/v2/heartbeat`

**Embedding Dimension**: 1024 (Titan Embeddings V2)

**Metadata Constraints**:
- No None values allowed
- All values must be JSON-serializable
- Coordinates stored as separate latitude/longitude fields (not nested)

**Query Parameters** (for similarity search):
```python
{
  "query_embeddings": [[1024-dim vector]],
  "n_results": 10,
  "where": {"city": "Bangalore"},  # Optional metadata filter
  "include": ["documents", "metadatas", "distances"]
}
```

**No TTL**: ChromaDB documents persist indefinitely (manual cleanup required)


### S3 Bucket

**Bucket Name**: roadsense-raw-signals-778277577994

**Purpose**: Signal backup and static website hosting

**Signal Storage**:
- Key format: `signals/{signal_id}.json`
- ContentType: application/json
- Triggers: Inference Lambda on ObjectCreated events

**Signal Object Structure**:
```json
{
  "signal_id": "uuid",
  "source": "news|weather",
  "source_name": "gnews_blr_pothole|...",
  "original_content": "text",
  "translated_content": "english text",
  "detected_language": "hi|en|...",
  "city": "Bangalore",
  "timestamp": "ISO8601",
  "scraped_at": "ISO8601",
  "ingested_at": "ISO8601",
  "location": {
    "coordinates": {"lat": 12.97, "lon": 77.59},
    "accuracy_meters": 500,
    "address": "MG Road, Bangalore"
  },
  "weather_data": {...},
  "classification": {...},
  "intent": {...}
}
```

**Event Notifications**:
- Event type: s3:ObjectCreated:*
- Prefix filter: signals/
- Destination: Inference Lambda ARN

**Static Website Hosting**:
- Index document: index.html
- Error document: error.html
- CloudFront origin: S3 bucket website endpoint

**Encryption**: Server-side encryption (SSE-S3)

**Versioning**: Disabled (signals are immutable)

**Lifecycle Policy**: None (signals expire via DynamoDB TTL, not S3)


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Signal ID Determinism

For any signal with the same content and timestamp, the generated signal_id should be identical across multiple invocations.

**Validates: Requirements 1.6**

### Property 2: Deduplication Correctness

For any set of signals containing duplicates (same signal_id), only one instance of each unique signal_id should be written to DynamoDB.

**Validates: Requirements 1.5, 3.5, 3.6, 17.3**

### Property 3: Error Isolation in Scraping

For any RSS feed that fails during scraping, all other feeds should still be processed and their signals collected.

**Validates: Requirements 1.8, 15.1**

### Property 4: Translation Preservation

For any signal, both original_content and translated_content fields should be present in the stored signal, and detected_language should be populated.

**Validates: Requirements 2.3, 2.4, 17.8**

### Property 5: English Signal Optimization

For any signal where detected_language is "en", the translation API should not be invoked, and translated_content should equal original_content.

**Validates: Requirements 2.5**

### Property 6: Translation Fallback

For any signal where translation fails, translated_content should equal original_content and a warning should be logged.

**Validates: Requirements 2.6**

### Property 7: TTL Calculation

For any signal written to DynamoDB, the ttl attribute should equal the current timestamp plus exactly 30 days (2,592,000 seconds).

**Validates: Requirements 3.2**

### Property 8: Float to Decimal Conversion

For any signal containing float values in location or weather_data fields, all floats should be converted to Decimal type before DynamoDB write.

**Validates: Requirements 3.4**

### Property 9: Scraped Timestamp Presence

For any signal written to DynamoDB, the scraped_at field should be present and contain a valid ISO8601 timestamp.

**Validates: Requirements 3.7**

### Property 10: Stream Event Filtering

For any DynamoDB Stream event with eventName "MODIFY" or "REMOVE", the Ingest Lambda should skip processing and return immediately.

**Validates: Requirements 4.2**

### Property 11: Embedding Dimension Validation

For any embedding generated by Titan Embeddings V2, the dimension should be exactly 1024, otherwise a ValueError should be raised.

**Validates: Requirements 4.6, 4.7**

### Property 12: ChromaDB Metadata Cleaning

For any signal metadata stored in ChromaDB, all None values should be removed before the HTTP POST request.

**Validates: Requirements 5.3**

### Property 13: S3 Key Format

For any signal written to S3, the object key should follow the format "signals/{signal_id}.json" where signal_id is the signal's UUID.

**Validates: Requirements 6.4**

### Property 14: Ingestion Timestamp Addition

For any signal written to S3, an ingested_at field should be added containing the timestamp when Ingest Lambda processed it.

**Validates: Requirements 6.2**

### Property 15: Location Structure Normalization

For any signal processed by the normalizer, the location field should be a dict with coordinates (containing lat and lon as floats), accuracy_meters, and address subfields.

**Validates: Requirements 7.2, 7.3**

### Property 16: Required Field Validation

For any signal processed by the normalizer, signal_id and translated_content must be present and non-empty, otherwise validation should fail.

**Validates: Requirements 7.6**

### Property 17: Classification Confidence Bounds

For any signal classified by the Classification Agent, the confidence score should be between 0.01 and 0.99 (never exactly 0.0 or 1.0).

**Validates: Requirements 8.5**

### Property 18: Damage Type Enum Validation

For any signal classified as road-related, the damage_type should be one of: "pothole", "surface_wear", "flooding", "general", or null.

**Validates: Requirements 8.4**

### Property 19: Weather Signal Pre-Classification

For any signal where source equals "weather", the Classification Agent should not invoke the AI model, and should return is_road_related=true, damage_type="flooding", confidence=0.75.

**Validates: Requirements 8.11, 16.7**

### Property 20: Mumbai Signal Filtering

For any signal where location.address contains "mumbai" (case-insensitive), the Classification Agent should return is_road_related=false, confidence=0.0.

**Validates: Requirements 8.12, 16.8**

### Property 21: Classification Fallback

For any signal where the AI model response cannot be parsed, the Classification Agent should return is_road_related=false, confidence=0.1.

**Validates: Requirements 8.13**

### Property 22: Intent Confidence Modifier Bounds

For any signal processed by the Intent Agent, the confidence_modifier should be between -0.4 and +0.2.

**Validates: Requirements 9.6**

### Property 23: Intent Confidence Adjustment

For any signal processed by the Intent Agent, the final classification confidence should equal the original confidence plus the confidence_modifier, clamped to [0.01, 0.99].

**Validates: Requirements 9.7**

### Property 24: Weather Signal Intent Pre-Classification

For any signal where source equals "weather", the Intent Agent should not invoke the AI model, and should return is_problem_report=true, urgency_level="medium", context_type="weather_alert".

**Validates: Requirements 9.12, 16.9**

### Property 25: News Signal Context Classification

For any signal where source equals "news", the Intent Agent should classify context_type as "news_article".

**Validates: Requirements 9.13**

### Property 26: Intent Fallback

For any signal where the AI model response cannot be parsed, the Intent Agent should return is_problem_report=true, confidence_modifier=0.0.

**Validates: Requirements 9.14**

### Property 27: Correlation Eligibility Filtering

For any set of signals, only those where (is_road_related=true AND is_problem_report=true) OR source="weather" should be eligible for clustering.

**Validates: Requirements 10.1, 10.2**

### Property 28: Temporal Relation

For any two signals with timestamps within 7 days (604,800 seconds) of each other, they should be considered temporally related.

**Validates: Requirements 10.5**

### Property 29: Geographic Relation

For any two signals with coordinates within 500 meters (Haversine distance) OR with the same city name (when coordinates are missing), they should be considered geographically related.

**Validates: Requirements 10.6, 10.7, 17.6**

### Property 30: Semantic Similarity

For any two signal embeddings with cosine similarity ≥ 0.75, they should be considered semantically similar.

**Validates: Requirements 10.8**

### Property 31: Clustering Criteria

For any two signals that are temporally related AND geographically related AND semantically similar, they should be grouped into the same cluster.

**Validates: Requirements 10.9**

### Property 32: Cluster ID Determinism

For any set of signal IDs, the generated cluster_id should be deterministic (same input signal IDs produce same cluster_id).

**Validates: Requirements 10.15**

### Property 33: Cluster Centroid Calculation

For any cluster with N signals having coordinates, the center_coordinates should be the arithmetic mean of all signal coordinates.

**Validates: Requirements 10.12**

### Property 34: Source Diversity Uniqueness

For any cluster, the source_diversity list should contain only unique source_name values (no duplicates).

**Validates: Requirements 10.14**

### Property 35: Confidence Score Bounds

For any cluster processed by the Inference Agent, the confidence_score should be between 0 and 100 (inclusive).

**Validates: Requirements 11.1, 11.10**

### Property 36: Weather Correlation Bonus

For any cluster containing at least one signal where source="weather", the confidence_score should include a +10 point bonus.

**Validates: Requirements 11.7**

### Property 37: Source Diversity Bonus

For any cluster with 3 or more distinct sources, the confidence_score should include a +10 point bonus; for 2 distinct sources, a +5 point bonus.

**Validates: Requirements 11.8, 11.9**

### Property 38: Severity Level Determination

For any cluster with confidence_score ≥ 85 OR containing any signal with urgency_level="critical", severity_level should be "critical". For confidence_score ≥ 65 OR urgency_level="high", severity_level should be "high". For confidence_score ≥ 45, severity_level should be "medium". Otherwise, severity_level should be "low".

**Validates: Requirements 11.11, 11.12, 11.13, 11.14**

### Property 39: Incident Creation Threshold

For any cluster with confidence_score ≤ 30, no incident should be created.

**Validates: Requirements 11.15, 11.16**

### Property 40: Confidence History Recording

For any incident created, the confidence_history field should contain at least one entry with timestamp, confidence_score, and reason fields.

**Validates: Requirements 11.17**

### Property 41: Explanation Length Constraint

For any incident explanation generated, the character count should not exceed 600 characters.

**Validates: Requirements 12.10**

### Property 42: Explanation Bullet Point Prohibition

For any incident explanation generated, the text should not contain bullet point characters (•, -, *, etc. at line start).

**Validates: Requirements 12.9**

### Property 43: Explanation Technical Term Prohibition

For any incident explanation generated, the text should not contain the words "confidence", "score", "embedding", "vector", or other technical terms.

**Validates: Requirements 12.8**

### Property 44: Explanation Fallback

For any incident where the AI model fails to generate an explanation, a fallback explanation should be constructed from structured incident data.

**Validates: Requirements 12.11**

### Property 45: Incident Field Completeness

For any incident written to DynamoDB, all required fields (incident_id, cluster_id, damage_type, severity_level, confidence_score, status, explanation, signal_count, signal_ids, source_diversity, location, confidence_history, created_at, updated_at) should be present.

**Validates: Requirements 13.2**

### Property 46: Incident JSON Serialization

For any incident written to DynamoDB, the location and confidence_history fields should be stored as JSON strings, not nested objects.

**Validates: Requirements 13.3**

### Property 47: Decimal to Native Type Conversion

For any incident containing Decimal values, all Decimals should be converted to int or float before JSON serialization.

**Validates: Requirements 13.4**

### Property 48: New Incident Status

For any newly created incident, the status field should be set to "active".

**Validates: Requirements 13.5**

### Property 49: Empty Value Filtering

For any incident written to DynamoDB, all fields with empty string ("") or None values should be removed before the write operation.

**Validates: Requirements 13.7**

### Property 50: Scheduled Event Detection

For any Lambda event where event.source equals "aws.events" OR event does not contain "Records" field, the Inference Lambda should execute in scheduled batch mode.

**Validates: Requirements 14.1**

### Property 51: Batch Size Limit

For any DynamoDB scan operation in scheduled mode, the Limit parameter should be set to 100.

**Validates: Requirements 14.3**

### Property 52: Empty Result Handling

For any execution where no clusters are formed OR no incidents meet the confidence threshold, the Inference Lambda should return HTTP 200 with incidents_created=0.

**Validates: Requirements 14.8, 14.9**

### Property 53: Batch Processing Independence

For any DynamoDB Stream batch containing multiple records, each record should be processed independently such that one record's failure does not prevent processing of other records.

**Validates: Requirements 15.2, 15.3**

### Property 54: Ingest Lambda Status Code

For any execution of Ingest Lambda, the HTTP status code should be 200 regardless of individual signal processing failures.

**Validates: Requirements 15.4**

### Property 55: AI Model Fallback

For any AI agent where model invocation fails, fallback logic should be applied and a warning should be logged.

**Validates: Requirements 15.6**

### Property 56: JSON Parse Fallback

For any JSON parsing operation that fails, default values should be used and a warning should be logged.

**Validates: Requirements 15.7**

### Property 57: Inference Lambda Error Response

For any unhandled exception in Inference Lambda, the response should have HTTP status code 500 and include error details.

**Validates: Requirements 15.10**

### Property 58: Translated Content Fallback

For any signal where translated_content is empty or None, agents should use original_content as the text input.

**Validates: Requirements 17.5**

### Property 59: Timestamp Fallback

For any signal with missing or invalid timestamp, the Correlation Agent should assume the signal is within the time window.

**Validates: Requirements 17.7**


## Error Handling

### Scraper Lambda Error Handling

**Per-Source Isolation**:
- Each RSS feed and weather API call is wrapped in try-except
- One source failure does not block other sources
- Failed sources are logged with `exc_info=True`
- Summary includes failed count for monitoring

**Secrets Manager Fallback**:
- Checks environment variables before calling Secrets Manager
- Logs warning if secrets unavailable
- Continues execution with empty API keys (scrapers return empty results)

**Translation Errors**:
- Falls back to original_content if translation fails
- Logs warning with language code and error details
- Never blocks signal processing

**DynamoDB Write Errors**:
- Conditional put failures (duplicates) are logged at debug level
- Other write errors are logged at error level
- Failed writes increment failed counter
- Batch continues processing remaining signals

### Ingest Lambda Error Handling

**Validation Errors**:
- Missing required fields: Log warning, return failed status
- Invalid field types: Log warning, return failed status
- Never raises exceptions that would trigger Lambda retry

**Embedding Generation Errors**:
- Bedrock API failures: Log error, return failed status
- Invalid embedding dimension: Raise ValueError (caught by caller)
- Timeout errors: Log error, return failed status

**ChromaDB Errors**:
- Connection failures: Raise RuntimeError with connection details
- HTTP errors: Raise RuntimeError with status code and body
- Heartbeat failures: Log error but continue processing

**S3 Write Errors**:
- Write failures: Log error, return failed status
- Never blocks other signals in batch

**Batch Processing**:
- Always returns HTTP 200 to prevent Lambda retry
- Individual signal failures are logged and tracked
- Returns summary with succeeded/failed counts

### Inference Lambda Error Handling

**S3 Read Errors**:
- Wrapped in try-except
- Returns HTTP 500 with error details
- Logs full exception with `exc_info=True`

**Agent Failures**:
- Classification/Intent: Apply fallback logic, log warning
- Correlation: Log error, return empty clusters
- Inference: Log error, return empty incidents
- Explanation: Use fallback explanation, log warning

**DynamoDB Errors**:
- Write failures: Log error, continue processing
- Scan failures: Log error, return HTTP 500
- Batch writer errors: Log error, continue with next batch

**JSON Parsing Errors**:
- Parse failures: Use default values, log warning
- Serialization failures: Convert Decimal to native types, retry

**Model Response Parsing**:
- Invalid JSON: Apply fallback logic
- Missing fields: Use default values
- Invalid enum values: Use default from valid set

**Scheduled Mode Errors**:
- No signals found: Return HTTP 200 with 0 processed
- Classification failures: Log error, skip signal
- Correlation failures: Return HTTP 200 with 0 clusters


## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Specific RSS feed parsing examples
- Known location keyword matching
- Error handling for specific failure scenarios
- Integration points between components
- AWS service mock interactions

**Property-Based Tests**: Verify universal properties across all inputs
- Signal ID generation determinism
- Deduplication correctness
- Confidence score bounds
- Clustering algorithm correctness
- Data transformation invariants

Together, unit tests catch concrete bugs while property tests verify general correctness across the input space.

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python (industry standard for property-based testing)

**Test Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)  # Minimum 100 iterations per property
@given(signal=signal_strategy())
def test_property_1_signal_id_determinism(signal):
    """
    Feature: roadsense-ai-system, Property 1: Signal ID Determinism
    For any signal with the same content and timestamp, the generated 
    signal_id should be identical across multiple invocations.
    """
    id1 = generate_signal_id(signal["content"], signal["timestamp"])
    id2 = generate_signal_id(signal["content"], signal["timestamp"])
    assert id1 == id2
```

**Tagging Convention**:
Each property test must include a docstring comment referencing the design document:
```
Feature: {feature_name}, Property {number}: {property_text}
```

**Minimum Iterations**: 100 examples per property test (due to randomization)

**Test Organization**:
```
tests/
  unit/
    test_scraper_lambda.py
    test_ingest_lambda.py
    test_inference_lambda.py
    test_classification_agent.py
    test_intent_agent.py
    test_correlation_agent.py
    test_inference_agent.py
    test_explanation_agent.py
  property/
    test_signal_properties.py
    test_classification_properties.py
    test_correlation_properties.py
    test_inference_properties.py
  integration/
    test_end_to_end.py
```

### Unit Test Focus Areas

**Scraper Lambda**:
- RSS feed parsing with known articles
- Weather API response parsing
- Language detection for specific texts
- Location keyword matching for known areas
- Deduplication with known duplicate signals
- Error handling for specific feed failures

**Ingest Lambda**:
- DynamoDB Stream record parsing
- Embedding generation with mock Bedrock
- ChromaDB API request formatting
- S3 write with mock S3 client
- Batch processing with mixed success/failure

**Classification Agent**:
- Known pothole descriptions → damage_type="pothole"
- Known flooding descriptions → damage_type="flooding"
- Weather signals → pre-classification
- Mumbai signals → filtered out
- Model response parsing with known JSON

**Intent Agent**:
- Known sarcastic text → negative confidence modifier
- Known direct reports → positive confidence modifier
- Weather signals → pre-classification
- News signals → context_type="news_article"
- Model response parsing with known JSON

**Correlation Agent**:
- Known signal pairs within 500m → clustered
- Known signal pairs beyond 500m → not clustered
- Known signal pairs within 7 days → temporally related
- Known signal pairs beyond 7 days → not temporally related
- Cosine similarity calculation with known vectors

**Inference Agent**:
- Known cluster with 3 sources → source diversity bonus
- Known cluster with weather signal → weather bonus
- Known cluster with confidence 85 → severity="critical"
- Known cluster with confidence 30 → no incident created

**Explanation Agent**:
- Known incident → explanation contains location
- Known incident with translated signals → mentions languages
- Known incident → explanation length ≤ 600 chars
- Model failure → fallback explanation generated

### Property Test Focus Areas

**Signal Processing Properties**:
- Property 1: Signal ID determinism
- Property 2: Deduplication correctness
- Property 3: Error isolation in scraping
- Property 4: Translation preservation
- Property 5: English signal optimization
- Property 6: Translation fallback
- Property 7: TTL calculation
- Property 8: Float to Decimal conversion
- Property 9: Scraped timestamp presence

**Classification Properties**:
- Property 17: Classification confidence bounds
- Property 18: Damage type enum validation
- Property 19: Weather signal pre-classification
- Property 20: Mumbai signal filtering
- Property 21: Classification fallback

**Intent Properties**:
- Property 22: Intent confidence modifier bounds
- Property 23: Intent confidence adjustment
- Property 24: Weather signal intent pre-classification
- Property 25: News signal context classification
- Property 26: Intent fallback

**Correlation Properties**:
- Property 27: Correlation eligibility filtering
- Property 28: Temporal relation
- Property 29: Geographic relation
- Property 30: Semantic similarity
- Property 31: Clustering criteria
- Property 32: Cluster ID determinism
- Property 33: Cluster centroid calculation
- Property 34: Source diversity uniqueness

**Inference Properties**:
- Property 35: Confidence score bounds
- Property 36: Weather correlation bonus
- Property 37: Source diversity bonus
- Property 38: Severity level determination
- Property 39: Incident creation threshold
- Property 40: Confidence history recording

**Explanation Properties**:
- Property 41: Explanation length constraint
- Property 42: Explanation bullet point prohibition
- Property 43: Explanation technical term prohibition
- Property 44: Explanation fallback

**Data Persistence Properties**:
- Property 45: Incident field completeness
- Property 46: Incident JSON serialization
- Property 47: Decimal to native type conversion
- Property 48: New incident status
- Property 49: Empty value filtering

**Error Handling Properties**:
- Property 53: Batch processing independence
- Property 54: Ingest Lambda status code
- Property 55: AI model fallback
- Property 56: JSON parse fallback
- Property 57: Inference Lambda error response
- Property 58: Translated content fallback
- Property 59: Timestamp fallback

### Integration Testing

**End-to-End Flow**:
1. Mock RSS feed with known articles
2. Mock weather API with known conditions
3. Verify signals written to DynamoDB
4. Verify embeddings stored in ChromaDB
5. Verify signals written to S3
6. Verify incidents created in DynamoDB
7. Verify incident explanations generated

**AWS Service Mocking**:
- Use `moto` for DynamoDB, S3, Secrets Manager mocking
- Use `unittest.mock` for Bedrock, Translate, ChromaDB
- Verify correct API calls with expected parameters

**Performance Testing**:
- Measure Scraper Lambda execution time (target: <30s)
- Measure Ingest Lambda execution time (target: <5s per signal)
- Measure Inference Lambda execution time (target: <60s)
- Verify batch processing handles 100 signals

### Test Data Generators

**Hypothesis Strategies**:
```python
import hypothesis.strategies as st

# Signal strategy
signal_strategy = st.fixed_dictionaries({
    "signal_id": st.uuids().map(str),
    "source": st.sampled_from(["news", "weather"]),
    "source_name": st.sampled_from(["reddit", "youtube", "times_of_india", "openweathermap"]),
    "original_content": st.text(min_size=10, max_size=500),
    "translated_content": st.text(min_size=10, max_size=500),
    "detected_language": st.sampled_from(["en", "hi", "ta", "te", "kn"]),
    "city": st.just("Bangalore"),
    "timestamp": st.datetimes().map(lambda dt: dt.isoformat()),
    "location": location_strategy(),
})

# Location strategy
location_strategy = st.fixed_dictionaries({
    "coordinates": st.fixed_dictionaries({
        "lat": st.floats(min_value=12.8, max_value=13.2),
        "lon": st.floats(min_value=77.4, max_value=77.8),
    }),
    "accuracy_meters": st.integers(min_value=50, max_value=5000),
    "address": st.text(min_size=5, max_size=100),
})

# Classification strategy
classification_strategy = st.fixed_dictionaries({
    "is_road_related": st.booleans(),
    "damage_type": st.sampled_from(["pothole", "surface_wear", "flooding", "general", None]),
    "confidence": st.floats(min_value=0.01, max_value=0.99),
    "reasoning": st.text(min_size=10, max_size=200),
})

# Intent strategy
intent_strategy = st.fixed_dictionaries({
    "is_problem_report": st.booleans(),
    "urgency_level": st.sampled_from(["low", "medium", "high", "critical"]),
    "context_type": st.sampled_from(["direct_report", "indirect_mention", "news_article", "weather_alert", "speculation", "sarcasm", "ambiguous"]),
    "confidence_modifier": st.floats(min_value=-0.4, max_value=0.2),
    "reasoning": st.text(min_size=10, max_size=200),
})
```

### Continuous Integration

**Test Execution**:
- Run unit tests on every commit
- Run property tests on every pull request
- Run integration tests before deployment
- Generate coverage reports (target: >80%)

**Test Environments**:
- Local: Mock all AWS services
- CI: Mock all AWS services
- Staging: Use real AWS services with test data
- Production: Monitor with CloudWatch metrics


## Infrastructure Design

### AWS Lambda Configuration

**Scraper Lambda**:
```yaml
FunctionName: roadsense-scraper
Runtime: python3.12
Handler: lambda_function.lambda_handler
Timeout: 60 seconds
Memory: 512 MB
Environment:
  DYNAMODB_TABLE: roadsense-signals
  SCRAPER_SECRETS_NAME: roadsense/scraper-keys
  AWS_REGION: us-east-1
Triggers:
  - EventBridge: rate(1 hour)
IAM Role Permissions:
  - dynamodb:PutItem (roadsense-signals)
  - secretsmanager:GetSecretValue (roadsense/scraper-keys)
  - translate:TranslateText
  - translate:DetectDominantLanguage
```

**Ingest Lambda**:
```yaml
FunctionName: roadsense-ingest
Runtime: python3.12
Handler: lambda_function.lambda_handler
Timeout: 30 seconds
Memory: 1024 MB
Environment:
  CHROMA_HOST: 98.80.183.42
  CHROMA_PORT: 8000
  BEDROCK_REGION: us-east-1
  EMBED_MODEL_ID: amazon.titan-embed-text-v2:0
  S3_BUCKET: roadsense-raw-signals-778277577994
Triggers:
  - DynamoDB Stream: roadsense-signals (NEW_IMAGE)
IAM Role Permissions:
  - dynamodb:GetRecords
  - dynamodb:GetShardIterator
  - dynamodb:DescribeStream
  - dynamodb:ListStreams
  - bedrock:InvokeModel (amazon.titan-embed-text-v2:0)
  - s3:PutObject (roadsense-raw-signals-*)
```

**Inference Lambda**:
```yaml
FunctionName: roadsense-inference
Runtime: python3.12
Handler: inference_lambda.lambda_handler
Timeout: 120 seconds
Memory: 2048 MB
Environment:
  S3_BUCKET: roadsense-raw-signals-778277577994
  DYNAMODB_REGION: us-east-1
  SIGNALS_TABLE: roadsense-signals
  INCIDENTS_TABLE: roadsense-incidents
  BEDROCK_REGION: us-east-1
Triggers:
  - S3: ObjectCreated (prefix: signals/)
  - EventBridge: rate(5 minutes)
IAM Role Permissions:
  - s3:GetObject (roadsense-raw-signals-*)
  - dynamodb:Scan (roadsense-signals)
  - dynamodb:BatchWriteItem (roadsense-signals, roadsense-incidents)
  - bedrock:InvokeModel (amazon.nova-micro-v1:0)
  - bedrock:InvokeModel (amazon.nova-lite-v1:0)
  - bedrock:InvokeModel (amazon.titan-embed-text-v2:0)
```

### DynamoDB Configuration

**Signals Table**:
```yaml
TableName: roadsense-signals
BillingMode: PAY_PER_REQUEST
KeySchema:
  - AttributeName: signal_id
    KeyType: HASH
AttributeDefinitions:
  - AttributeName: signal_id
    AttributeType: S
StreamSpecification:
  StreamEnabled: true
  StreamViewType: NEW_IMAGE
TimeToLiveSpecification:
  Enabled: true
  AttributeName: ttl
PointInTimeRecoverySpecification:
  PointInTimeRecoveryEnabled: true
SSESpecification:
  Enabled: true
  SSEType: KMS
```

**Incidents Table**:
```yaml
TableName: roadsense-incidents
BillingMode: PAY_PER_REQUEST
KeySchema:
  - AttributeName: incident_id
    KeyType: HASH
AttributeDefinitions:
  - AttributeName: incident_id
    AttributeType: S
PointInTimeRecoverySpecification:
  PointInTimeRecoveryEnabled: true
SSESpecification:
  Enabled: true
  SSEType: KMS
```

### S3 Configuration

**Bucket**:
```yaml
BucketName: roadsense-raw-signals-778277577994
Region: us-east-1
Versioning: Disabled
Encryption:
  SSEAlgorithm: AES256
NotificationConfiguration:
  LambdaFunctionConfigurations:
    - LambdaFunctionArn: arn:aws:lambda:us-east-1:778277577994:function:roadsense-inference
      Events:
        - s3:ObjectCreated:*
      Filter:
        Key:
          FilterRules:
            - Name: prefix
              Value: signals/
WebsiteConfiguration:
  IndexDocument: index.html
  ErrorDocument: error.html
PublicAccessBlockConfiguration:
  BlockPublicAcls: false
  IgnorePublicAcls: false
  BlockPublicPolicy: false
  RestrictPublicBuckets: false
```

### EventBridge Configuration

**Scraper Schedule**:
```yaml
RuleName: roadsense-scraper-hourly
ScheduleExpression: rate(1 hour)
State: ENABLED
Targets:
  - Arn: arn:aws:lambda:us-east-1:778277577994:function:roadsense-scraper
    Id: roadsense-scraper-target
```

**Inference Batch Schedule**:
```yaml
RuleName: roadsense-inference-batch
ScheduleExpression: rate(5 minutes)
State: ENABLED
Targets:
  - Arn: arn:aws:lambda:us-east-1:778277577994:function:roadsense-inference
    Id: roadsense-inference-target
```

### ChromaDB EC2 Configuration

**Instance**:
```yaml
InstanceType: t3.medium
AMI: Ubuntu 22.04 LTS
Storage: 50 GB gp3
SecurityGroup:
  Ingress:
    - Port: 8000
      Protocol: TCP
      Source: Lambda Security Group
    - Port: 22
      Protocol: TCP
      Source: Admin IP
  Egress:
    - All traffic
```

**ChromaDB Setup**:
```bash
# Install ChromaDB
pip install chromadb

# Run ChromaDB server
chroma run --host 0.0.0.0 --port 8000

# Create collection
curl -X POST http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "roadsense-signals", "metadata": {"dimension": 1024}}'
```

### CloudFront Configuration

**Distribution**:
```yaml
Origins:
  - DomainName: roadsense-raw-signals-778277577994.s3-website-us-east-1.amazonaws.com
    Id: S3-roadsense-raw-signals
    CustomOriginConfig:
      HTTPPort: 80
      OriginProtocolPolicy: http-only
DefaultCacheBehavior:
  TargetOriginId: S3-roadsense-raw-signals
  ViewerProtocolPolicy: redirect-to-https
  AllowedMethods:
    - GET
    - HEAD
  CachedMethods:
    - GET
    - HEAD
  Compress: true
  DefaultTTL: 86400
PriceClass: PriceClass_100
Enabled: true
```

### Secrets Manager Configuration

**Scraper Keys Secret**:
```yaml
SecretName: roadsense/scraper-keys
SecretString:
  OPENWEATHER_API_KEY: <api-key>
KmsKeyId: alias/aws/secretsmanager
```

### IAM Roles

**Scraper Lambda Role**:
```yaml
RoleName: roadsense-scraper-role
AssumeRolePolicyDocument:
  Version: "2012-10-17"
  Statement:
    - Effect: Allow
      Principal:
        Service: lambda.amazonaws.com
      Action: sts:AssumeRole
ManagedPolicyArns:
  - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
Policies:
  - PolicyName: roadsense-scraper-policy
    PolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Action:
            - dynamodb:PutItem
          Resource: arn:aws:dynamodb:us-east-1:778277577994:table/roadsense-signals
        - Effect: Allow
          Action:
            - secretsmanager:GetSecretValue
          Resource: arn:aws:secretsmanager:us-east-1:778277577994:secret:roadsense/scraper-keys-*
        - Effect: Allow
          Action:
            - translate:TranslateText
            - translate:DetectDominantLanguage
          Resource: "*"
```

**Ingest Lambda Role**:
```yaml
RoleName: roadsense-ingest-role
AssumeRolePolicyDocument:
  Version: "2012-10-17"
  Statement:
    - Effect: Allow
      Principal:
        Service: lambda.amazonaws.com
      Action: sts:AssumeRole
ManagedPolicyArns:
  - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
Policies:
  - PolicyName: roadsense-ingest-policy
    PolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Action:
            - dynamodb:GetRecords
            - dynamodb:GetShardIterator
            - dynamodb:DescribeStream
            - dynamodb:ListStreams
          Resource: arn:aws:dynamodb:us-east-1:778277577994:table/roadsense-signals/stream/*
        - Effect: Allow
          Action:
            - bedrock:InvokeModel
          Resource: arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0
        - Effect: Allow
          Action:
            - s3:PutObject
          Resource: arn:aws:s3:::roadsense-raw-signals-778277577994/signals/*
```

**Inference Lambda Role**:
```yaml
RoleName: roadsense-inference-role
AssumeRolePolicyDocument:
  Version: "2012-10-17"
  Statement:
    - Effect: Allow
      Principal:
        Service: lambda.amazonaws.com
      Action: sts:AssumeRole
ManagedPolicyArns:
  - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
Policies:
  - PolicyName: roadsense-inference-policy
    PolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Action:
            - s3:GetObject
          Resource: arn:aws:s3:::roadsense-raw-signals-778277577994/signals/*
        - Effect: Allow
          Action:
            - dynamodb:Scan
            - dynamodb:BatchWriteItem
          Resource:
            - arn:aws:dynamodb:us-east-1:778277577994:table/roadsense-signals
            - arn:aws:dynamodb:us-east-1:778277577994:table/roadsense-incidents
        - Effect: Allow
          Action:
            - bedrock:InvokeModel
          Resource:
            - arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0
            - arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0
            - arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0
```

### Network Configuration

**VPC** (optional for ChromaDB access):
```yaml
VpcId: vpc-xxxxx
Subnets:
  - subnet-xxxxx (us-east-1a)
  - subnet-xxxxx (us-east-1b)
SecurityGroups:
  - sg-lambda (Lambda functions)
  - sg-chromadb (ChromaDB EC2)
```

**Security Group Rules**:
```yaml
sg-lambda:
  Egress:
    - Port: 8000
      Protocol: TCP
      Destination: sg-chromadb
    - Port: 443
      Protocol: TCP
      Destination: 0.0.0.0/0

sg-chromadb:
  Ingress:
    - Port: 8000
      Protocol: TCP
      Source: sg-lambda
  Egress:
    - All traffic
```

### Cost Estimation

**Monthly Costs** (estimated for 5-10 signals/hour, 200-400 incidents/month):

| Service | Usage | Cost |
|---------|-------|------|
| Lambda (Scraper) | 720 invocations × 30s × 512MB | $0.50 |
| Lambda (Ingest) | 200 invocations × 5s × 1024MB | $0.30 |
| Lambda (Inference) | 200 + 8640 invocations × 60s × 2048MB | $15.00 |
| DynamoDB (Signals) | 200 writes, 10K reads, 5GB storage | $2.00 |
| DynamoDB (Incidents) | 200 writes, 1K reads, 1GB storage | $0.50 |
| S3 | 200 writes, 10K reads, 5GB storage | $0.50 |
| Bedrock (Nova Micro) | 400 invocations × 1K tokens | $2.00 |
| Bedrock (Nova Lite) | 200 invocations × 2K tokens | $3.00 |
| Bedrock (Titan Embeddings) | 400 invocations × 500 tokens | $1.00 |
| Translate | 200 translations × 500 chars | $1.00 |
| EC2 (ChromaDB) | t3.medium × 730 hours | $30.00 |
| CloudFront | 10GB transfer | $1.00 |
| Secrets Manager | 1 secret × 730 hours | $0.40 |
| **Total** | | **$57.20** |

**Cost Optimization Strategies**:
- Pre-classify weather signals (saves Bedrock calls)
- Filter Mumbai signals early (saves Bedrock calls)
- Use DynamoDB on-demand pricing (no idle costs)
- Use S3 Intelligent-Tiering for old signals
- Consider Reserved Instance for ChromaDB EC2
- Batch Bedrock invocations where possible


## Security Design

### Authentication and Authorization

**AWS Service Authentication**:
- All Lambda functions use IAM roles for AWS service access
- No hardcoded credentials in code or environment variables
- Principle of least privilege: Each Lambda has minimal required permissions
- IAM policies scoped to specific resources (tables, buckets, models)

**API Key Management**:
- OpenWeatherMap API key stored in AWS Secrets Manager
- Secrets Manager accessed via IAM role permissions
- Fallback to environment variables for local development only
- Secrets rotation: Manual rotation every 90 days

**ChromaDB Access**:
- EC2 security group restricts access to Lambda security group only
- No public internet access to ChromaDB port 8000
- HTTP API (no authentication) - secured by network isolation
- Consider adding API key authentication for production

### Data Encryption

**At Rest**:
- DynamoDB: Server-side encryption with AWS KMS
- S3: Server-side encryption with AES-256 (SSE-S3)
- Secrets Manager: Encrypted with AWS managed KMS key
- EC2 volumes: EBS encryption enabled

**In Transit**:
- All AWS service calls use HTTPS (TLS 1.2+)
- ChromaDB HTTP API: Consider adding TLS termination via ALB
- CloudFront: HTTPS enforced (redirect HTTP to HTTPS)
- Bedrock API: HTTPS with AWS Signature V4

### Access Control

**Lambda Execution Roles**:
- Scraper Lambda: DynamoDB write, Secrets Manager read, Translate access
- Ingest Lambda: DynamoDB Stream read, Bedrock invoke, S3 write
- Inference Lambda: S3 read, DynamoDB read/write, Bedrock invoke

**DynamoDB Access**:
- Signals table: Write access for Scraper, read access for Inference
- Incidents table: Write access for Inference only
- No public access, no cross-account access
- Point-in-time recovery enabled for data protection

**S3 Access**:
- Signals prefix: Write access for Ingest, read access for Inference
- Website hosting: Public read access for dashboard files only
- Bucket policy restricts access to specific Lambda roles
- No public write access

**Bedrock Access**:
- Model access restricted to specific foundation models
- No fine-tuning or custom model access
- Usage tracked via CloudWatch metrics
- Consider AWS Organizations SCP for model restrictions

### Data Privacy

**PII Handling**:
- No PII collected from RSS feeds or weather APIs
- Location data is public (city-level, road names)
- No user authentication or personal accounts
- No tracking of individual users

**Data Retention**:
- Signals: 30-day TTL (automatic deletion)
- Incidents: Permanent (no TTL) for audit trail
- ChromaDB: Manual cleanup required (no TTL)
- S3: Consider lifecycle policy for old signals

**Data Minimization**:
- Only collect necessary fields from sources
- No storage of full RSS feed content
- No storage of raw weather API responses
- Metadata limited to operational needs

### Network Security

**VPC Configuration** (optional):
- Lambda functions can run in VPC for ChromaDB access
- Private subnets with NAT Gateway for internet access
- Security groups restrict traffic between components
- VPC endpoints for AWS services (DynamoDB, S3, Secrets Manager)

**Security Group Rules**:
- Lambda SG: Outbound to ChromaDB (8000), AWS services (443)
- ChromaDB SG: Inbound from Lambda SG only (8000)
- No inbound SSH except from admin IP (22)
- All other traffic denied by default

**DDoS Protection**:
- CloudFront provides Layer 3/4 DDoS protection
- AWS Shield Standard enabled by default
- Rate limiting on EventBridge schedules
- Lambda concurrency limits prevent runaway costs

### Secrets Management

**Secrets Manager Best Practices**:
- One secret per environment (dev, staging, prod)
- Secret name: `roadsense/scraper-keys`
- JSON format for multiple keys
- Automatic rotation: Not enabled (manual rotation every 90 days)
- Access logging via CloudTrail

**Secret Structure**:
```json
{
  "OPENWEATHER_API_KEY": "api-key-value"
}
```

**Access Pattern**:
1. Lambda checks environment variables first (local dev)
2. If not found, calls Secrets Manager (production)
3. Caches secret value for Lambda execution lifetime
4. Logs warning if secret unavailable

### Audit and Compliance

**CloudTrail Logging**:
- All AWS API calls logged to CloudTrail
- S3 bucket for CloudTrail logs with encryption
- Log retention: 90 days
- Alerts on suspicious activity (IAM changes, unauthorized access)

**CloudWatch Logging**:
- All Lambda functions log to CloudWatch Logs
- Log retention: 30 days
- Structured logging with JSON format
- Log levels: INFO, WARNING, ERROR

**Monitoring and Alerting**:
- CloudWatch alarms for Lambda errors
- CloudWatch alarms for DynamoDB throttling
- CloudWatch alarms for Bedrock quota limits
- SNS notifications for critical alerts

**Compliance Considerations**:
- No GDPR requirements (no personal data)
- No HIPAA requirements (no health data)
- No PCI DSS requirements (no payment data)
- Public data only (news articles, weather)

### Vulnerability Management

**Dependency Management**:
- Python dependencies: Use `pip-audit` for vulnerability scanning
- Lambda runtime: Use latest Python 3.12 runtime
- Regular updates: Monthly dependency updates
- Automated scanning: GitHub Dependabot or Snyk

**Code Security**:
- No SQL injection (DynamoDB NoSQL)
- No command injection (no shell commands)
- Input validation on all external data
- Output encoding for web dashboard

**Infrastructure Security**:
- EC2 instance: Regular OS updates (Ubuntu LTS)
- Security patches: Automated with AWS Systems Manager
- AMI updates: Quarterly rebuild with latest patches
- SSH key rotation: Every 90 days

### Incident Response

**Security Incident Playbook**:
1. Detect: CloudWatch alarms, CloudTrail logs
2. Contain: Disable Lambda functions, revoke IAM roles
3. Investigate: Review CloudTrail logs, Lambda logs
4. Remediate: Rotate secrets, patch vulnerabilities
5. Recover: Re-enable functions, monitor for recurrence
6. Document: Post-incident report, lessons learned

**Backup and Recovery**:
- DynamoDB: Point-in-time recovery enabled
- S3: Versioning disabled (signals are immutable)
- Secrets Manager: Automatic backup with recovery
- EC2: Regular AMI snapshots (weekly)

**Disaster Recovery**:
- RTO (Recovery Time Objective): 4 hours
- RPO (Recovery Point Objective): 1 hour
- Multi-region: Not implemented (single region us-east-1)
- Backup region: Consider us-west-2 for DR


## Performance Design

### Latency Optimization

**Scraper Lambda**:
- Target: 30 seconds average execution time
- Parallel RSS feed fetching: Use `concurrent.futures.ThreadPoolExecutor`
- Connection pooling: Reuse HTTP connections across feeds
- Timeout configuration: 10 seconds per feed (fail fast)
- Batch DynamoDB writes: Use batch_writer for multiple signals

**Ingest Lambda**:
- Target: 5 seconds per signal
- Bedrock connection reuse: Initialize client once per execution
- ChromaDB connection pooling: Reuse HTTP session
- S3 write optimization: Use multipart upload for large signals
- Parallel processing: Process DynamoDB Stream batch records concurrently

**Inference Lambda**:
- Target: 60 seconds for single signal processing
- Agent pipeline optimization: Reuse Bedrock client across agents
- DynamoDB batch operations: Use batch_writer for signals and incidents
- Parallel agent invocation: Run classification and intent in parallel where possible
- Caching: Cache embeddings in memory for correlation step

### Throughput Optimization

**Scraper Lambda**:
- Expected throughput: 5-10 signals per hour
- Concurrency: 1 (hourly schedule, no concurrent executions)
- Batch size: Process all feeds in single execution
- Error handling: Per-feed isolation prevents cascading failures

**Ingest Lambda**:
- Expected throughput: 5-10 signals per hour
- Concurrency: Up to 10 (DynamoDB Stream batch size)
- Batch processing: Process multiple stream records in parallel
- Error handling: Per-record isolation prevents batch retry

**Inference Lambda**:
- Expected throughput: 5-10 signals per hour (real-time) + 100 signals per 5 minutes (batch)
- Concurrency: Up to 100 (S3 triggers + scheduled events)
- Reserved concurrency: 50 (prevent runaway costs)
- Batch size: 100 signals per scheduled execution

### Scalability

**Horizontal Scaling**:
- Lambda: Automatic scaling up to reserved concurrency limit
- DynamoDB: On-demand capacity mode (automatic scaling)
- S3: Unlimited scalability
- ChromaDB: Single EC2 instance (bottleneck)

**Vertical Scaling**:
- Scraper Lambda: 512 MB memory (sufficient for RSS parsing)
- Ingest Lambda: 1024 MB memory (sufficient for embeddings)
- Inference Lambda: 2048 MB memory (required for 5-stage pipeline)
- ChromaDB EC2: t3.medium (2 vCPU, 4 GB RAM)

**Scaling Limits**:
- Lambda concurrency: 1000 (AWS account limit)
- DynamoDB throughput: Unlimited (on-demand mode)
- Bedrock quota: 10,000 requests per minute (Nova Micro)
- ChromaDB: Single instance limit (~1000 queries per second)

**Scaling Strategy**:
- Phase 1 (current): Single region, single ChromaDB instance
- Phase 2 (10x growth): Add read replicas for ChromaDB
- Phase 3 (100x growth): Multi-region deployment with regional ChromaDB
- Phase 4 (1000x growth): Managed vector database (Pinecone, Weaviate)

### Caching Strategy

**Lambda Execution Context Reuse**:
- Bedrock client: Initialize once, reuse across invocations
- DynamoDB client: Initialize once, reuse across invocations
- S3 client: Initialize once, reuse across invocations
- Secrets Manager: Cache secrets for execution lifetime

**Embedding Cache**:
- In-memory cache: Store embeddings during correlation step
- Cache key: signal_id
- Cache lifetime: Single Lambda execution
- Cache size: Up to 100 signals × 1024 floats × 4 bytes = 400 KB

**No External Cache**:
- No Redis or ElastiCache (adds cost and complexity)
- No DynamoDB caching (signals change infrequently)
- No CloudFront caching for API responses (no API Gateway)

### Database Optimization

**DynamoDB Performance**:
- On-demand capacity: No provisioned throughput to manage
- Partition key: signal_id (UUID) ensures even distribution
- No hot partitions: Random UUIDs prevent hotspots
- Batch operations: Use batch_writer for multiple items
- Consistent reads: Not required (eventual consistency acceptable)

**DynamoDB Streams**:
- Stream view type: NEW_IMAGE (only new items, not old)
- Batch size: 100 records (default)
- Batch window: 0 seconds (process immediately)
- Retry policy: 2 retries with exponential backoff

**ChromaDB Performance**:
- HTTP API: Faster than gRPC for small batches
- Batch inserts: Insert multiple documents in single request
- Query optimization: Use metadata filters to reduce search space
- Index type: HNSW (Hierarchical Navigable Small World)

### Cost Optimization

**Lambda Optimization**:
- Right-size memory: Use minimum memory that meets performance targets
- Reduce execution time: Optimize code paths, use parallel processing
- Reserved concurrency: Prevent runaway costs from infinite loops
- Arm64 architecture: Consider Graviton2 for 20% cost savings

**DynamoDB Optimization**:
- On-demand pricing: No idle costs, pay per request
- TTL: Automatic deletion of old signals (no manual cleanup)
- Batch operations: Reduce number of API calls
- Projection expressions: Fetch only required attributes

**Bedrock Optimization**:
- Pre-classification: Skip AI models for weather and Mumbai signals
- Batch invocations: Process multiple signals in single request (if supported)
- Model selection: Use Nova Micro (cheapest) for classification/intent
- Token optimization: Minimize prompt length, use structured output

**S3 Optimization**:
- Lifecycle policies: Move old signals to Glacier after 90 days
- Intelligent-Tiering: Automatic cost optimization for infrequent access
- Compression: Gzip JSON files before upload
- Multipart upload: Only for files >5 MB (not needed for signals)

**EC2 Optimization**:
- Reserved Instance: 1-year commitment for 40% savings
- Spot Instance: Not suitable (ChromaDB requires high availability)
- Right-sizing: Monitor CPU/memory usage, downsize if underutilized
- Auto-scaling: Not implemented (single instance sufficient)

### Monitoring and Alerting

**CloudWatch Metrics**:
- Lambda duration: P50, P90, P99 latencies
- Lambda errors: Error count, error rate
- Lambda throttles: Throttle count, throttle rate
- DynamoDB consumed capacity: Read/write capacity units
- DynamoDB throttles: Throttle count, throttle rate
- Bedrock invocations: Request count, error count
- Bedrock latency: P50, P90, P99 latencies

**Custom Metrics**:
- Signals collected per hour: Scraper Lambda
- Signals processed per hour: Ingest Lambda
- Incidents created per hour: Inference Lambda
- Classification accuracy: Percentage of correct classifications
- False positive rate: Percentage of incorrect incidents

**CloudWatch Alarms**:
- Lambda errors > 5 in 5 minutes: Critical
- Lambda duration > 60 seconds: Warning
- DynamoDB throttles > 10 in 5 minutes: Critical
- Bedrock errors > 10 in 5 minutes: Critical
- Signals collected < 3 per hour: Warning

**CloudWatch Dashboards**:
- System overview: Signals, incidents, errors
- Lambda performance: Duration, errors, throttles
- DynamoDB performance: Consumed capacity, throttles
- Bedrock performance: Invocations, latency, errors
- Cost tracking: Estimated daily/monthly costs

### Performance Testing

**Load Testing**:
- Simulate 100 signals per hour (10x normal load)
- Measure Lambda execution times under load
- Verify DynamoDB throughput under load
- Verify ChromaDB query performance under load

**Stress Testing**:
- Simulate 1000 signals per hour (100x normal load)
- Identify bottlenecks (ChromaDB, Bedrock quotas)
- Measure Lambda throttling behavior
- Verify error handling under extreme load

**Endurance Testing**:
- Run system for 24 hours at normal load
- Monitor for memory leaks in Lambda functions
- Monitor for ChromaDB performance degradation
- Verify TTL cleanup works correctly

**Benchmarking**:
- Baseline: Current performance metrics
- Target: 92% classification accuracy, <8% false positive rate
- SLA: 99.9% uptime, <60s incident creation latency
- Cost: $25-35 per month

