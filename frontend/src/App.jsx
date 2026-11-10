import { useState, useEffect, useMemo, useContext } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Icon from "@mui/material/Icon";
import MDBox from "components/MDBox";
import Sidenav from "examples/Sidenav";
import Configurator from "examples/Configurator";
import theme from "assets/theme";
import themeRTL from "assets/theme/theme-rtl";
import themeDark from "assets/theme-dark";
import themeDarkRTL from "assets/theme-dark/theme-rtl";
import rtlPlugin from "stylis-plugin-rtl";
import { CacheProvider } from "@emotion/react";
import createCache from "@emotion/cache";
import routes from "routes";
import { useMaterialUIController, setMiniSidenav, setOpenConfigurator } from "context";
import brandWhite from "assets/images/logo-ct.png";
import brandDark from "assets/images/logo-ct-dark.png";
import { setupAxiosInterceptors } from "./services/interceptor";
import ProtectedRoute from "examples/ProtectedRoute";
import ForgotPassword from "auth/forgot-password";
import ResetPassword from "auth/reset-password";
import Login from "auth/login";
import Register from "auth/register";
import { AuthContext, getRoleHomePath } from "context";
import UserProfile from "layouts/user-profile";

export default function App() {
  const authContext = useContext(AuthContext);
  const [controller, dispatch] = useMaterialUIController();
  const {
    miniSidenav, direction, layout, openConfigurator, sidenavColor,
    transparentSidenav, whiteSidenav, darkMode,
  } = controller;
  const [onMouseEnter, setOnMouseEnter] = useState(false);
  const rtlCache = useMemo(() => createCache({ key: "rtl", stylisPlugins: [rtlPlugin] }), []);
  const { pathname } = useLocation();

  const handleOnMouseEnter = () => {
    if (miniSidenav && !onMouseEnter) {
      setMiniSidenav(dispatch, false);
      setOnMouseEnter(true);
    }
  };

  const handleOnMouseLeave = () => {
    if (onMouseEnter) {
      setMiniSidenav(dispatch, true);
      setOnMouseEnter(false);
    }
  };

  const handleConfiguratorOpen = () => setOpenConfigurator(dispatch, !openConfigurator);
  const navigate = useNavigate();
  setupAxiosInterceptors(() => {
    authContext.logout();
    navigate("/auth/login");
  });

  useEffect(() => {
    document.body.setAttribute("dir", direction);
  }, [direction]);

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.scrollingElement.scrollTop = 0;
  }, [pathname]);

  const getRoutes = (allRoutes) => allRoutes.map((route) => {
    if (route.collapse) return getRoutes(route.collapse);
    if (route.route && route.type !== "auth") {
      return (
        <Route
          exact
          path={route.route}
          element={
            <ProtectedRoute isAuthenticated={authContext.isAuthenticated} isLoading={authContext.isLoading} user={authContext.user} allowedRoles={route.allowedRoles}>
              {route.component}
            </ProtectedRoute>
          }
          key={route.key}
        />
      );
    }
    return null;
  });

  const configsButton = (
    <MDBox
      display={{ xs: "none", sm: "flex" }}
      justifyContent="center"
      alignItems="center"
      width="3.25rem"
      height="3.25rem"
      bgColor="white"
      shadow="sm"
      borderRadius="50%"
      position="fixed"
      right="2rem"
      bottom="2rem"
      zIndex={99}
      color="dark"
      sx={{ cursor: "pointer" }}
      onClick={handleConfiguratorOpen}
    >
      <Icon fontSize="small" color="inherit">settings</Icon>
    </MDBox>
  );

  const applicationShell = (
    <>
      {layout === "dashboard" && authContext.isAuthenticated && (
        <>
          <Sidenav
            color={sidenavColor}
            brand={(transparentSidenav && !darkMode) || whiteSidenav ? brandDark : brandWhite}
            brandName="Meditrust"
            routes={routes}
            onMouseEnter={handleOnMouseEnter}
            onMouseLeave={handleOnMouseLeave}
          />
          <Configurator />
          {configsButton}
        </>
      )}
      {layout === "vr" && <Configurator />}
    </>
  );

  return (
    <>
      {direction === "rtl" ? (
        <CacheProvider value={rtlCache}>
          <ThemeProvider theme={darkMode ? themeDarkRTL : themeRTL}>
            <CssBaseline />
            {applicationShell}
            <Routes>
              <Route path="login" element={<Navigate to="/auth/login" />} />
              <Route path="register" element={<Navigate to="/auth/register" />} />
              <Route path="forgot-password" element={<Navigate to="/auth/forgot-password" />} />
              {getRoutes(routes)}
              <Route path="/" element={<Navigate to={authContext.isAuthenticated ? getRoleHomePath(authContext.user?.role) : "/auth/login"} replace />} />
            <Route path="*" element={<Navigate to={authContext.isAuthenticated ? getRoleHomePath(authContext.user?.role) : "/auth/login"} replace />} />
            </Routes>
          </ThemeProvider>
        </CacheProvider>
      ) : (
        <ThemeProvider theme={darkMode ? themeDark : theme}>
          <CssBaseline />
          {applicationShell}
          <Routes>
            <Route path="/auth/login" element={<Login />} />
            <Route path="/auth/register" element={<Register />} />
            <Route path="/auth/forgot-password" element={<ForgotPassword />} />
            <Route path="/auth/reset-password" element={<ResetPassword />} />
            <Route
              exact
              path="/user-profile"
              element={
                <ProtectedRoute isAuthenticated={authContext.isAuthenticated} isLoading={authContext.isLoading} user={authContext.user}>
                  <UserProfile />
                </ProtectedRoute>
              }
              key="user-profile"
            />

            {getRoutes(routes)}
            <Route path="/" element={<Navigate to={authContext.isAuthenticated ? getRoleHomePath(authContext.user?.role) : "/auth/login"} replace />} />
            <Route path="*" element={<Navigate to={authContext.isAuthenticated ? getRoleHomePath(authContext.user?.role) : "/auth/login"} replace />} />
          </Routes>
        </ThemeProvider>
      )}
    </>
  );
}
