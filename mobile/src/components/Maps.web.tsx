/**
 * Wrapper carte — version WEB (navigateur).
 *
 * react-native-maps importe des modules internes de React Native (codegen)
 * qui n'existent pas sur le web : l'importer casse le bundle. On expose donc
 * des stubs inertes. Sur le web, MAPS_ENABLED vaut false (voir @constants),
 * donc ces composants ne sont jamais rendus — ils existent seulement pour
 * satisfaire l'import.
 */
import React from 'react';

const Noop: React.FC<Record<string, unknown>> = () => null;

export default Noop;
export const Marker = Noop;
export const Circle = Noop;
export const PROVIDER_DEFAULT = undefined;
export const PROVIDER_GOOGLE = undefined;

export type MapViewProps = Record<string, unknown>;
export type Region = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};
