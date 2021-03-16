import typing
from logging import Logger

from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import config_integration
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.trace import execution_context
from opencensus.trace.propagation.trace_context_http_header_format import TraceContextPropagator

from azure.functions import (
    AppExtensionBase, Context, FunctionExtensionException
)


class OpenCensusExtension(AppExtensionBase):
    @classmethod
    def init(cls):
        config_integration.trace_integrations(['requests'])
        cls.configured = False

    @classmethod
    def configure(cls, appinsight_key: str, *args, **kwargs):
        cls.exporter: AzureExporter = AzureExporter(instrumentation_key=appinsight_key)
        cls.configured: bool = True
        cls.tracer: Tracer = None

    @classmethod
    def pre_invocation_app_level(cls, logger: Logger, context: Context, func_args: typing.Dict[str, object], *args, **kwargs) -> None:
        if not cls.configured:
            raise FunctionExtensionException(
                'OpenCensusExtension.configure(appinsight_key=) is not called, '
                'failed to invoke opencensus extension.'
            )
        logger.warning(f'pre_invocation_app_level: {context.trace_context.Traceparent}')
        logger.warning(f'pre_invocation_app_level id context: {id(context)}')
        span_context = TraceContextPropagator().from_headers({
            "traceparent": context.trace_context.Traceparent,
            "tracestate": context.trace_context.Tracestate
        })

        tracer = Tracer(
            span_context=span_context,
            exporter=cls.exporter,
            sampler=ProbabilitySampler(1.0)
        )
        execution_context.set_opencensus_tracer(tracer)

        logger.warning(f'function_name: {context.function_name}')
        logger.warning(f'{context.function_name} traceparent: {context.trace_context.Traceparent}')
        logger.warning(f'{context.function_name} tracestate: {context.trace_context.Tracestate}')
        setattr(context, 'tracer', tracer)
        logger.info(f'Attached tracer to {context.function_name}')