/**
 * Wrapper carte — version NATIVE (Android / iOS).
 *
 * Réexporte react-native-maps tel quel. La version `.web.tsx` fournit des stubs
 * pour le navigateur, où react-native-maps n'existe pas (imports natifs).
 */
export { default, Marker, Circle, PROVIDER_DEFAULT, PROVIDER_GOOGLE } from 'react-native-maps';
export type { MapViewProps, Region } from 'react-native-maps';
