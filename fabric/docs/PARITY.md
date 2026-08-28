# Platform parity contract

Fabric must call the shared `schads_audit` modules directly and must not reimplement Award arithmetic in Fabric notebooks. This guarantees calculations can be regression-tested once and deployed to both platforms.