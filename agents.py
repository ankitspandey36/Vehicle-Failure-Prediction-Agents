def agent_ingestion(
    vehicle_id: str,
    car_type: str,
    available_sensor_fields: dict,
    vehicle_state_api,
    realtime_data_api,
    snapshot_data_api,
    llm_client=None,
):
    """
    GENAI INGESTION AGENT
    -----------------------
    - If vehicle is ON (WORKING): collect ALL telemetry once.
    - If vehicle is OFF (NOT_WORKING): LLM selects NECESSARY fields (no limit).
    - Returns clean payload for next agent.
    """

    import time, json

    # Determine vehicle working state
    raw_state = vehicle_state_api(vehicle_id)
    state = "WORKING" if str(raw_state).lower() in ("on", "working", "running", "true") else "NOT_WORKING"

    # ---------------------------------------------------------------------
    # HIGH FREQUENCY MODE — Vehicle is ON
    # ---------------------------------------------------------------------
    if state == "WORKING":
        fields = list(available_sensor_fields.keys())
        data = realtime_data_api(vehicle_id, fields)

        return {
            "vehicle_id": vehicle_id,
            "car_type": car_type,
            "mode": "HIGH_FREQ",
            "timestamp": time.time(),
            "selected_fields": fields,
            "data": data
        }

    # ---------------------------------------------------------------------
    # LOW FREQUENCY MODE — Vehicle is OFF
    # LLM chooses NECESSARY fields (no limit)
    # ---------------------------------------------------------------------
    fields_text = "\n".join(f"- {f}" for f in available_sensor_fields.keys())

    prompt = f"""
You are an advanced automotive diagnostic LLM.

Vehicle type: {car_type}

Here are ALL available telemetry fields:
{fields_text}

The vehicle is currently OFF.

Your task:
- Select ALL telemetry fields that are NECESSARY to assess vehicle health when the engine is OFF.
- Include battery, electrical, temperature, parking-related, or any other field needed for a health snapshot.
- You may choose ANY number of fields (no limit).
- Output ONLY a JSON array of field names.
"""

    selected_fields = []

    if llm_client:
        try:
            resp = llm_client(prompt)
            selected_fields = json.loads(resp) if isinstance(resp, str) else resp
        except:
            selected_fields = []

    # If LLM fails → fallback to ALL fields (safe option)
    if not selected_fields:
        selected_fields = list(available_sensor_fields.keys())

    # Fetch snapshot only for those fields
    data = snapshot_data_api(vehicle_id, selected_fields)

    return {
        "vehicle_id": vehicle_id,
        "car_type": car_type,
        "mode": "LOW_FREQ",
        "timestamp": time.time(),
        "selected_fields": selected_fields,
        "data": data
    }











def genai_data_analysis_agent(
    ingestion_payload: dict,
    llm_client
):
    """
    GENAI DATA ANALYSIS AGENT (LLM-ONLY)
    ------------------------------------
    Now performs:
    - LLM-based anomaly detection (no math)
    - LLM reasoning
    - LLM summary
    - LLM early warning signals
    - LLM recommended actions

    Works BETWEEN:
    Ingestion Agent → Data Analysis Agent → Diagnosis Agent
    """

    import json, time, traceback

    try:
        # Build a refined GenAI prompt
        prompt = f"""
You are an automotive expert GenAI agent.

You will receive REAL telemetry or snapshot data from the ingestion agent.

Your tasks:

1. **Detect anomalies or unusual values** in the telemetry.
   - Use reasoning, NOT statistical formulas.
   - Compare values against typical automotive expectations.
   - Example anomalies:
       • abnormal engine temperature
       • low battery voltage
       • inconsistent RPM vs speed
       • pressure values out of expected range
       • sudden drops or spikes
       • sensor values that contradict each other

2. **Explain WHY each anomaly might be happening** (reasoning step).

3. **Summarize the vehicle's current condition** in simple language.

4. **Suggest 3–5 recommended actions** (maintenance, inspection, adjustments).

5. Output ONLY valid JSON with keys:
   {
     "summary": "...",
     "anomalies": [...],
     "possible_causes": [...],
     "recommendations": [...]
   }

Here is the actual telemetry data:
{json.dumps(ingestion_payload, indent=2)}
"""

        # Call the LLM
        llm_response = llm_client(prompt)

        # Parse JSON
        if isinstance(llm_response, dict):
            genai = llm_response
        else:
            try:
                genai = json.loads(llm_response)
            except Exception:
                genai = {
                    "summary": llm_response,
                    "anomalies": [],
                    "possible_causes": [],
                    "recommendations": []
                }

        # Build final structured output
        final_output = {
            "vehicle_id": ingestion_payload.get("vehicle_id"),
            "timestamp": time.time(),
            "analysis_result": genai
        }

        return final_output

    except Exception as e:
        traceback.print_exc()
        return {
            "error": "genai_analysis_failed",
            "details": str(e)
        }









def diagnosis_agent(
    ingestion_payload: dict,
    tf_model=None,
    xgb_model=None,
    llm_client=None
):
    """
    ADVANCED DIAGNOSIS AGENT
    -------------------------
    Performs:
      - ML-based failure prediction (TensorFlow)
      - ML-based priority scoring (XGBoost)
      - GenAI-based Root Cause Analysis (RCA)
      - GenAI-based Corrective & Preventive Actions (CAPA)

    Input: ingestion agent payload
    Output: diagnosis JSON
    """

    import numpy as np
    import json
    import time
    import traceback

    vehicle_id = ingestion_payload.get("vehicle_id")
    data = ingestion_payload.get("data", {})
    fields = ingestion_payload.get("selected_fields", list(data.keys()))

    # ---------------------------------------------------------
    # 1. Build model input vector
    # ---------------------------------------------------------
    try:
        feature_names = sorted(fields)
        model_input = np.array([
            float(data.get(f, 0)) if isinstance(data.get(f), (int, float)) else 0
            for f in feature_names
        ]).reshape(1, -1)
    except:
        model_input = np.zeros((1, len(fields)))

    # ---------------------------------------------------------
    # 2. TensorFlow Failure Probability
    # ---------------------------------------------------------
    failure_probability = None
    if tf_model:
        try:
            failure_probability = float(tf_model.predict(model_input)[0][0])
        except:
            failure_probability = None

    # ---------------------------------------------------------
    # 3. XGBoost Priority Score
    # ---------------------------------------------------------
    priority_score = None
    if xgb_model:
        try:
            priority_score = float(xgb_model.predict(model_input)[0])
        except:
            priority_score = None

    # ---------------------------------------------------------
    # 4. GENAI ROOT CAUSE + CAPA (Main Part)
    # ---------------------------------------------------------
    rca = {}
    capa = {}

    if llm_client:
        try:
            prompt = f"""
You are an expert automotive diagnostic LLM.

Given the following vehicle telemetry data and ML predictions:

Telemetry Data:
{json.dumps(data, indent=2)}

ML Predictions:
- Failure Probability: {failure_probability}
- Priority Score: {priority_score}

Your tasks:

1. Identify the MOST LIKELY ROOT CAUSES (RCA):
   - List possible causes of the issue
   - Explain why each cause is likely, referencing the telemetry patterns

2. Provide CAPA (Corrective and Preventive Actions):
   - Give 3–5 corrective actions (immediate fixes)
   - Give 3–5 preventive actions (future avoidance)
   - Keep each action short and practical

3. Summarize vehicle condition clearly:
   - Severity level (Low/Medium/High/Critical)
   - Confidence based on ML scores

Output JSON ONLY with keys:
{
  "root_causes": [...],
  "corrective_actions": [...],
  "preventive_actions": [...],
  "severity": "...",
  "explanation": "..."
}
"""

            resp = llm_client(prompt)

            try:
                genai = json.loads(resp)
            except:
                genai = {"explanation": resp}

            rca = genai.get("root_causes", [])
            capa = {
                "corrective_actions": genai.get("corrective_actions", []),
                "preventive_actions": genai.get("preventive_actions", [])
            }
            severity = genai.get("severity", "unknown")
            explanation = genai.get("explanation", "")

        except:
            severity = "unknown"
            explanation = "LLM RCA/CAPA failed."
            rca = []
            capa = {}

    # ---------------------------------------------------------
    # 5. Final structured diagnosis output
    # ---------------------------------------------------------
    diagnosis_output = {
        "vehicle_id": vehicle_id,
        "timestamp": time.time(),
        "failure_probability": failure_probability,
        "priority_score": priority_score,
        "root_cause_analysis": rca,
        "CAPA": capa,
        "severity": severity,
        "explanation": explanation,
        "raw_data": data,
        "features_used": feature_names
    }

    return diagnosis_output














def manufacturing_insights_module(
    user_message: str,
    llm_client,
    pg_connection
):
    """
    MANUFACTURING INSIGHTS MODULE
    --------------------------------
    - Takes user text (voice-to-text handled externally)
    - Uses GPT-4 (via llm_client) to explain issues
    - Performs RCA + CAPA
    - Suggests nearest service type (not location-based)
    - Stores conversation in PostgreSQL
    - Returns a JSON-friendly dictionary
    """

    import json, traceback
    from datetime import datetime

    try:
        # ------------------------------
        # 1. Prepare LLM Prompt
        # ------------------------------
        prompt = f"""
You are an automotive manufacturing expert assistant.

User message:
\"{user_message}\"

Tasks:
1. Explain the issue the user may be facing based on their message.
2. Identify POSSIBLE ROOT CAUSES (RCA).
3. Provide CAPA (Corrective and Preventive Actions).
4. Suggest the TYPE of service center suitable (authorized, multi-brand, EV specialist).
5. Keep output short, practical, and in JSON format with keys:
   "explanation", "root_causes", "corrective_actions", "preventive_actions", "recommended_service_type"
"""

        # ------------------------------
        # 2. Query GPT-4 (or any LLM)
        # ------------------------------
        llm_response = llm_client(prompt)

        try:
            parsed = json.loads(llm_response)
        except:
            parsed = {"explanation": llm_response}

        # ------------------------------
        # 3. Store conversation in PostgreSQL
        # ------------------------------
        try:
            cursor = pg_connection.cursor()
            cursor.execute(
                """
                INSERT INTO conversations (timestamp, user_text, bot_response)
                VALUES (%s, %s, %s)
                """,
                (datetime.utcnow(), user_message, json.dumps(parsed))
            )
            pg_connection.commit()
        except Exception:
            traceback.print_exc()

        # ------------------------------
        # 4. Final Output
        # ------------------------------
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "user_message": user_message,
            "insights": parsed
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "error": "manufacturing_insights_failed",
            "details": str(e)
        }















def feedback_agent(
    user_message: str,
    llm_client,
    google_calendar_service,
    twilio_client,
    whatsapp_number: str,
    user_whatsapp: str
):
    """
    FEEDBACK & BOOKING AGENT
    ----------------------------------------------------
    - Takes user text feedback (or request for a booking)
    - Uses GPT (optional) to summarize user feedback
    - Checks Google Calendar for next available slot
    - Books a service appointment automatically
    - Sends confirmation to user via WhatsApp/Twilio
    - Returns JSON with booking + feedback status
    """

    import datetime
    import json
    import traceback

    try:
        # -------------------------------
        # 1. Use GPT to interpret feedback
        # -------------------------------
        prompt = f"""
You are an automotive customer feedback AI.

User said:
\"{user_message}\"

Tasks:
1. Summarize the feedback.
2. Detect if the user is requesting a service appointment.
3. Rate sentiment as: positive / neutral / negative.

Return JSON:
{{
  "summary": "...",
  "sentiment": "...",
  "needs_booking": true/false
}}
"""

        llm_resp = llm_client(prompt)
        try:
            interpretation = json.loads(llm_resp)
        except:
            interpretation = {
                "summary": llm_resp,
                "sentiment": "unknown",
                "needs_booking": False
            }

        # -------------------------------
        # 2. If booking is needed → find calendar slot
        # -------------------------------
        booking_info = None

        if interpretation.get("needs_booking", False):

            today = datetime.datetime.utcnow().date()

            # Check next 7 days for an empty 30-minute slot
            for day_offset in range(7):
                date_to_check = today + datetime.timedelta(days=day_offset)

                events = google_calendar_service.events().list(
                    calendarId="primary",
                    timeMin=datetime.datetime.combine(date_to_check, datetime.time(9, 0)).isoformat() + "Z",
                    timeMax=datetime.datetime.combine(date_to_check, datetime.time(18, 0)).isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime"
                ).execute().get("items", [])

                # find a free slot between 9:00–18:00  
                possible_start = datetime.datetime.combine(date_to_check, datetime.time(9, 0))

                for ev in events:
                    start = datetime.datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
                    if (start - possible_start).seconds >= 30 * 60:  # 30-minute gap
                        break
                    possible_start = datetime.datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))

                # If slot found before 18:00
                if possible_start.hour < 18:
                    start_time = possible_start
                    end_time = start_time + datetime.timedelta(minutes=30)

                    # Book it
                    event_body = {
                        "summary": "Vehicle Service Appointment",
                        "description": f"Booked automatically based on feedback: {user_message}",
                        "start": {"dateTime": start_time.isoformat() + "Z"},
                        "end": {"dateTime": end_time.isoformat() + "Z"}
                    }

                    created_event = google_calendar_service.events().insert(
                        calendarId="primary",
                        body=event_body
                    ).execute()

                    booking_info = {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat(),
                        "event_id": created_event.get("id")
                    }
                    break

        # -------------------------------
        # 3. WhatsApp Confirmation Message (Twilio)
        # -------------------------------
        if booking_info:
            msg = (f"Your service appointment is booked!\n\n"
                   f"🕒 Time: {booking_info['start']} - {booking_info['end']}\n"
                   f"📄 Summary: {interpretation.get('summary')}")
        else:
            msg = (f"Thanks for your feedback!\n\n"
                   f"Summary: {interpretation.get('summary')}\n"
                   f"Sentiment: {interpretation.get('sentiment')}")

        twilio_client.messages.create(
            from_=f"whatsapp:{whatsapp_number}",
            body=msg,
            to=f"whatsapp:{user_whatsapp}"
        )

        # -------------------------------
        # 4. Return clean JSON
        # -------------------------------
        return {
            "feedback_summary": interpretation.get("summary"),
            "sentiment": interpretation.get("sentiment"),
            "booking": booking_info,
            "message_sent": msg
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": "feedback_agent_failed", "details": str(e)}






def bert_sentiment_agent(
    service_id: str,
    user_feedback: str,
    bert_pipeline,
    db_connection
):
    """
    BERT SENTIMENT ANALYSIS AGENT
    ----------------------------------------------------
    - Takes post-service feedback text from the user
    - Uses a BERT sentiment model (HuggingFace pipeline)
    - Classifies feedback as: positive / neutral / negative
    - Updates the service record in the database
    - Returns a JSON result

    Parameters:
    - service_id: ID of the user's service session
    - user_feedback: text feedback
    - bert_pipeline: HuggingFace pipeline("sentiment-analysis")
    - db_connection: psycopg2 or any DB cursor connection
    """

    import time
    import traceback

    try:
        # ----------------------------------------
        # 1. Run BERT Sentiment Analysis
        # ----------------------------------------
        sentiment_output = bert_pipeline(user_feedback)[0]

        label = sentiment_output.get("label", "").lower()
        score = float(sentiment_output.get("score", 0))

        # Normalize labels (depends on model: "POSITIVE", "NEGATIVE", "NEUTRAL")
        if "pos" in label:
            sentiment = "positive"
        elif "neg" in label:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # ----------------------------------------
        # 2. Update the service record in database
        # ----------------------------------------
        try:
            cursor = db_connection.cursor()
            cursor.execute(
                """
                UPDATE service_records
                SET feedback_text = %s,
                    feedback_sentiment = %s,
                    sentiment_score = %s,
                    feedback_timestamp = NOW()
                WHERE service_id = %s
                """,
                (user_feedback, sentiment, score, service_id)
            )
            db_connection.commit()
        except Exception:
            traceback.print_exc()

        # ----------------------------------------
        # 3. Return clean JSON result
        # ----------------------------------------
        return {
            "service_id": service_id,
            "feedback": user_feedback,
            "sentiment": sentiment,
            "sentiment_score": score,
            "timestamp": time.time()
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "error": "bert_sentiment_agent_failed",
            "details": str(e)
        }








def quality_insights_agent(
    rca_capa_payload: dict,
    prediction_payload: dict,
    bigquery_client,
    tableau_client=None
):
    """
    QUALITY INSIGHTS AGENT
    ------------------------------------------------------
    Simulates the pipeline normally handled by:
      - Airflow (workflow scheduler)
      - BigQuery (manufacturing analytics warehouse)
      - Tableau (quality dashboards)

    This agent:
      1. Merges RCA/CAPA + predicted issues
      2. Creates manufacturing quality insights
      3. Writes insights to a BigQuery table
      4. (Optional) triggers Tableau extract refresh
      5. Returns structured insight JSON

    Parameters:
    - rca_capa_payload: output from diagnosis agent (with RCA, CAPA)
    - prediction_payload: ML predictions (failure scores, issue types)
    - bigquery_client: initialized BigQuery client object
    - tableau_client: optional API wrapper for Tableau refresh

    NOTE:
    This is a minimal GENAI-friendly agent function.
    """

    import time, traceback, json
    from datetime import datetime

    try:
        # --------------------------------------------------
        # 1. Merge Inputs
        # --------------------------------------------------
        vehicle_id = rca_capa_payload.get("vehicle_id")

        merged_insights = {
            "vehicle_id": vehicle_id,
            "timestamp": datetime.utcnow().isoformat(),
            "failure_probability": prediction_payload.get("failure_probability"),
            "priority_score": prediction_payload.get("priority_score"),
            "predicted_issue": prediction_payload.get("predicted_issue"),
            "root_causes": rca_capa_payload.get("root_cause_analysis"),
            "corrective_actions": rca_capa_payload.get("CAPA", {}).get("corrective_actions"),
            "preventive_actions": rca_capa_payload.get("CAPA", {}).get("preventive_actions"),
            "severity": rca_capa_payload.get("severity"),
            "explanation": rca_capa_payload.get("explanation"),
        }

        # --------------------------------------------------
        # 2. Insert into BigQuery (manufacturing quality warehouse)
        # --------------------------------------------------
        try:
            table_id = "manufacturing_dataset.quality_insights"

            rows_to_insert = [merged_insights]

            errors = bigquery_client.insert_rows_json(table_id, rows_to_insert)

            if errors:
                print("BigQuery Insert Errors:", errors)

        except Exception:
            traceback.print_exc()

        # --------------------------------------------------
        # 3. Trigger Tableau Refresh (optional)
        # --------------------------------------------------
        try:
            if tableau_client:
                tableau_client.trigger_refresh("Quality_Insights_Dashboard")
        except Exception:
            traceback.print_exc()

        # --------------------------------------------------
        # 4. Return Final Insight Bundle
        # --------------------------------------------------
        return {
            "status": "success",
            "quality_insights": merged_insights
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": "quality_insights_agent_failed", "details": str(e)}
