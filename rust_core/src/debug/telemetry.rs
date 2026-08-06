#[cfg(feature = "telemetry")]
use opentelemetry::{global, sdk::propagation::TraceContextPropagator};
#[cfg(feature = "telemetry")]
use opentelemetry_otlp::WithExportConfig;
#[cfg(feature = "telemetry")]
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

/// Initializes the OpenTelemetry tracing pipeline for Observability.
pub fn init_telemetry(_service_name: &str) {
    #[cfg(feature = "telemetry")]
    {
        println!(
            "🚀 [TELEMETRY] Initializing OpenTelemetry for service: {}",
            service_name
        );

        global::set_text_map_propagator(TraceContextPropagator::new());

        let tracer = opentelemetry_otlp::new_pipeline()
            .tracing()
            .with_exporter(
                opentelemetry_otlp::new_exporter()
                    .tonic()
                    .with_endpoint("http://localhost:4317"), // Default OTLP endpoint
            )
            .with_trace_config(opentelemetry::sdk::trace::config().with_resource(
                opentelemetry::sdk::Resource::new(vec![opentelemetry::KeyValue::new(
                    "service.name",
                    service_name.to_string(),
                )]),
            ))
            .install_batch(opentelemetry::runtime::Tokio)
            .expect("Failed to install OTLP tracer");

        let telemetry = tracing_opentelemetry::layer().with_tracer(tracer);

        tracing_subscriber::registry()
            .with(tracing_subscriber::EnvFilter::from_default_env())
            .with(telemetry)
            .init();

        println!("[TELEMETRY] Observability Active.");
    }

    #[cfg(not(feature = "telemetry"))]
    {
        println!("[TELEMETRY] Telemetry disabled. Enable 'telemetry' feature for observability.");
    }
}

/// Shuts down the telemetry pipeline.
pub fn shutdown_telemetry() {
    #[cfg(feature = "telemetry")]
    global::shutdown_tracer_provider();
}

/// [Phase 27] Reports high-density health metrics for the 7 Absolute Axioms.
pub fn report_axiomatic_health(axiom: u8, status: bool, metadata: &str) {
    if status {
        println!("[AXIOM_HEALTH] Axiom {}: OK ({})", axiom, metadata);
    } else {
        println!("[AXIOM_HEALTH] Axiom {}: BREACH! ({})", axiom, metadata);
    }

    #[cfg(feature = "telemetry")]
    {
        use tracing::{info, warn};
        if status {
            info!(
                axiom = axiom,
                status = "OK",
                metadata = metadata,
                "Axiomatic health report"
            );
        } else {
            warn!(
                axiom = axiom,
                status = "BREACH",
                metadata = metadata,
                "Axiomatic health report"
            );
        }
    }
}
