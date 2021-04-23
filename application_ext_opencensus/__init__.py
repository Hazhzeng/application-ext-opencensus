# Copyright 2019, OpenCensus Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from logging import Logger
from typing import List, Dict, Optional

from azure.functions import (
    Context,
    AppExtensionBase,
    FunctionExtensionException
)

from opencensus.trace import config_integration
from opencensus.trace.propagation.trace_context_http_header_format import (
    TraceContextPropagator
)
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.azure.trace_exporter import AzureExporter


# The app setting name for providing default opencensusu appinsights key
DEFAULT_INSTRUMENTATION_KEY_SETTING = 'APPINSIGHTS_INSTRUMENTATIONKEY'


class OpenCensusExtension(AppExtensionBase):
    @classmethod
    def init(cls):
        cls._tracers: Dict[str, Tracer] = {}
        cls._exporter: Optional[AzureExporter] = None
        cls._has_configure_called: bool = False
        cls._trace_integrations: List[str] = []
        cls._default_key: Optional[str] = os.environ.get(
            DEFAULT_INSTRUMENTATION_KEY_SETTING
        )

    @classmethod
    def configure(cls,
                  libraries: List[str],
                  instrumentation_key: Optional[str] = None,
                  *args,
                  **kwargs):
        """Configure libraries for integrating into OpenCensus extension.
        Initialize an Azure Exporter that will write traces to AppInsights.

        :type libraries: List[str]
        :param libraries: the libraries that need to be integrated into
            OpenCensus tracer. (e.g. ['requests'])
        :type instrumentation_key: Optional[str]
        :param instrumentation_key: the instrumentation key for azure exporter
            to write into. If this is set to None, the extension will write to
            the AppInsight resource defined in APPINSIGHTS_INSTRUMENTATIONKEY
        """
        cls._has_configure_called = True

        cls._trace_integrations = config_integration.trace_integrations(
            libraries
        )

        if not instrumentation_key and not cls._default_key:
            raise FunctionExtensionException(
                'Please ensure either instrumentation_key is passed into '
                'OpenCensusExtension.configure() method, or the app setting '
                'APPINSIGHTS_INSTRUMENTATIONKEY is provided.'
            )

        cls._exporter = AzureExporter(
            instrumentation_key=instrumentation_key or cls._default_key
        )

    @classmethod
    def pre_invocation_app_level(cls,
                                 logger: Logger,
                                 context: Context,
                                 func_args: Dict[str, object] = {},
                                 *args,
                                 **kwargs) -> None:
        if not cls._has_configure_called:
            raise FunctionExtensionException(
                'Please ensure OpenCensusExtension.configure() is called '
                'after the import OpenCensusExtension statement.'
            )

        span_context = TraceContextPropagator().from_headers({
            "traceparent": context.trace_context.Traceparent,
            "tracestate": context.trace_context.Tracestate
        })

        tracer = Tracer(
            span_context=span_context,
            exporter=cls._exporter,
            sampler=ProbabilitySampler(1.0)
        )

        cls._tracers[context.function_name] = tracer
        setattr(context, 'tracer', tracer)

    @classmethod
    def post_invocation_app_level(cls,
                                  logger: Logger,
                                  context: Context,
                                  func_args: Dict[str, object],
                                  func_ret: Optional[object],
                                  *args,
                                  **kwargs) -> None:
        if context.function_name in cls._tracers:
            cls._tracers[context.function_name].finish()
            del cls._tracers[context.function_name]
