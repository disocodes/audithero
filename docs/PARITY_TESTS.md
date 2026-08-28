# Cross-platform parity testing

For the same normalized fixtures, Databricks and Fabric must produce the same expected amount, review flags and reconciliation status. Platform adapters may alter storage metadata only. A future release gate can persist fixture outputs from both runtime self-tests and compare hashes.