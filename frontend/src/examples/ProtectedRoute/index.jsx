import { Navigate } from "react-router-dom";
import { getRoleHomePath } from "context";

const ProtectedRoute = ({ isAuthenticated, isLoading = false, user, allowedRoles, redirectPath = "/auth/login", children }) => {
  if (isLoading) return null;
  if (!isAuthenticated) return <Navigate to={redirectPath} replace />;
  if (allowedRoles && !allowedRoles.includes(user?.role)) return <Navigate to={getRoleHomePath(user?.role)} replace />;
  return children;
};
export default ProtectedRoute;
