SELECT
  region_id,
  metric_name,
  SUM(sample_size) AS sample_size,
  AVG(metric_value) AS metric_value,
  AVG(baseline_value) AS baseline_value,
  AVG(practical_significance) AS practical_significance
FROM regional_metric_snapshots_v1
WHERE snapshot_date >= current_date - INTERVAL '28' DAY
GROUP BY region_id, metric_name
HAVING SUM(sample_size) >= 30
ORDER BY metric_name, region_id;
