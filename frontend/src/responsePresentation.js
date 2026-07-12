export function reasoningState(response) {
  const rows = !response ? []
    : Array.isArray(response.turn_results) ? response.turn_results
      : response.scenario_results ? Object.values(response.scenario_results).flat()
        : [response];
  if (rows.length && rows.every((value) => value?.reasoning_available === undefined)) return "legacy";
  if (rows.some((value) => value?.reasoning_available)) return "available";
  return "unavailable";
}
