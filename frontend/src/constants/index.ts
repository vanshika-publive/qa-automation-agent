// --- Editor / Code panel ------------------------------------------------------
export const EDITOR_BG = '#0F172A';
export const EDITOR_BORDER = '#1E293B';
export const EDITOR_FONT_FAMILY = "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace";
export const EDITOR_LINE_HEIGHT = '20.8px';

// --- Icon style ---------------------------------------------------------------
// Applied to Google Material Symbols icons to use the filled variant.
export const FONT_VARIATION_FILLED = '"FILL" 1';

// --- Layout -------------------------------------------------------------------
export const SIDEBAR_WIDTH = 240;
export const COMPARE_PANEL_WIDTH = 480;

// --- API endpoints ------------------------------------------------------------
export const sseStreamUrl = (executionId: string): string =>
  `/api/executions/${executionId}/stream`;
