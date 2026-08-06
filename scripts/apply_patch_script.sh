
*** Begin Patch
*** Update File: model/agent/reflective_agent.py
@@
-    adp_risk = metrics.get("adp_risk_score")
-    if adp_risk is None:
-      adp_risk = metrics.get("adp_risk")
-    if adp_risk is None:
-      adp_risk = 1.0 - tau
-    try:
-      adp_risk = float(adp_risk)
-    except Exception:
-      adp_risk = 1.0
-    adp_risk = max(0.0, min(1.0, adp_risk))
+    adp_risk = metrics.get("adp_risk_score", metrics.get("adp_risk"))
+    if adp_risk is None:
+      adp_risk = 1.0 - tau
+    try:
+      adp_risk = float(adp_risk)
+    except Exception:
+      adp_risk = 1.0
+    adp_risk = max(0.0, min(1.0, adp_risk))
@@
-    proposal = {
-      "risk": adp_risk,
-      "requires_human_review": requires_review,
-    }
+    proposal = {
+      "risk": adp_risk,
+      "requires_human_review": requires_review,
+    }
*** End Patch
