import React from "react";
import { Navigate } from "react-router-dom";

/**
 * Mantiene compatibilidad con enlaces antiguos sin conservar el procesamiento
 * local sin autenticación. El flujo integrado vive en patient-capture.
 */
export default function Smartwatch() {
  return <Navigate to="/patient-capture" replace />;
}
