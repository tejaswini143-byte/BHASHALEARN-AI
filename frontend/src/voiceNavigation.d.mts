export type VoiceNavigationDestination = { label: string; path: string };
export function matchVoiceNavigationCommand(text: string): VoiceNavigationDestination | null;
