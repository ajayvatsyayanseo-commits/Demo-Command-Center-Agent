SELECT
  event_date,
  region_id,
  metric_name,
  COUNT(*) AS event_count,
  AVG(metric_value) AS average_value
FROM sanitized_demo_events_v1
WHERE event_date >= current_date - INTERVAL '28' DAY
GROUP BY event_date, region_id, metric_name
ORDER BY event_date DESC, region_id, metric_name;
