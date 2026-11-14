export type ScreenKey = 'home' | 'map' | 'compare' | 'assist';

export interface ScreenProps {
  selectedId: string;
  onSelect: (id: string) => void;
  go: (screen: ScreenKey) => void;
  /** Disaster event chosen on the damage map; null until the user picks one. */
  eventId: string | null;
  onEvent: (id: string) => void;
}
