import { type ToolSet } from "ai";
import { aggregator } from "./aggregator";
import { chartBuilder } from "./chart-builder";
import { instrumentDesigner } from "./instrument-designer";
import { panelSimulator } from "./panel-simulator";
import { personaGenerator } from "./persona-generator";
import { reportCompiler } from "./report-compiler";
import { secondaryResearch } from "./secondary-research";

export const tools = {
  personaGenerator,
  instrumentDesigner,
  panelSimulator,
  aggregator,
  chartBuilder,
  secondaryResearch,
  reportCompiler,
} satisfies ToolSet;
