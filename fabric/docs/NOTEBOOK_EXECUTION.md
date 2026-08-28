# Notebook execution

Fabric setup/self-test/BI notebook execution uses the current Core Job Scheduler path form `/items/{itemId}/jobs/RunNotebook/instances` (or the equivalent Notebook execution endpoint). Deployment must poll the resulting job instance to a terminal state and treat non-completion as failure.