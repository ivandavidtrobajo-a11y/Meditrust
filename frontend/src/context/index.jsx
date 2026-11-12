import { createContext, useContext, useReducer, useMemo, useState, useEffect } from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";
import AuthService from "services/auth-service";

const MaterialUI = createContext();
export const AuthContext = createContext({
  isAuthenticated: false, isLoading: true, user: null,
  login: () => {}, register: () => {}, logout: () => {},
});

export const getRoleHomePath = (role) => {
  if (role === "embarazada") return "/patient-dashboard";
  if (role === "medico") return "/doctor-dashboard";
  if (role === "admin") return "/dashboard";
  return "/auth/login";
};

const normalizeUser = (response) => {
  const profile = response?.data?.data || response?.data || response?.user || response;
  const attributes = profile?.attributes || profile || {};
  const id = profile?.id || attributes?.id;
  if (!id || !attributes?.role) return null;
  return { id: String(id), name: attributes.name || "", email: attributes.email || "",
    role: String(attributes.role).toLowerCase(), profile_image: attributes.profile_image || null };
};

const AuthContextProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    if (!localStorage.getItem("token")) {
      setIsLoading(false);
      return () => { active = false; };
    }
    AuthService.getProfile()
      .then((response) => {
        const currentUser = normalizeUser(response);
        if (!currentUser) throw new Error("La API no devolvió una identidad válida.");
        if (active) setUser(currentUser);
      })
      .catch(() => {
        localStorage.removeItem("token");
        if (active) setUser(null);
      })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  const login = (token, responseUser) => {
    const currentUser = normalizeUser(responseUser);
    if (!token || !currentUser) throw new Error("La respuesta de autenticación no contiene token y rol válidos.");
    localStorage.setItem("token", token);
    setUser(currentUser);
    navigate(getRoleHomePath(currentUser.role), { replace: true });
  };
  const register = (token, responseUser) => login(token, responseUser);
  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    navigate("/auth/login", { replace: true });
  };
  const value = useMemo(() => ({ isAuthenticated: Boolean(user), isLoading, user, login, register, logout }), [user, isLoading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

function reducer(state, action) {
  switch (action.type) {
    case "MINI_SIDENAV": return { ...state, miniSidenav: action.value };
    case "TRANSPARENT_SIDENAV": return { ...state, transparentSidenav: action.value };
    case "WHITE_SIDENAV": return { ...state, whiteSidenav: action.value };
    case "SIDENAV_COLOR": return { ...state, sidenavColor: action.value };
    case "TRANSPARENT_NAVBAR": return { ...state, transparentNavbar: action.value };
    case "FIXED_NAVBAR": return { ...state, fixedNavbar: action.value };
    case "OPEN_CONFIGURATOR": return { ...state, openConfigurator: action.value };
    case "DIRECTION": return { ...state, direction: action.value };
    case "LAYOUT": return { ...state, layout: action.value };
    case "DARKMODE": return { ...state, darkMode: action.value };
    default: throw new Error(`Unhandled action type: ${action.type}`);
  }
}

function MaterialUIControllerProvider({ children }) {
  const initialState = { miniSidenav: false, transparentSidenav: false, whiteSidenav: false,
    sidenavColor: "info", transparentNavbar: true, fixedNavbar: true, openConfigurator: false,
    direction: "ltr", layout: "dashboard", darkMode: false };
  const [controller, dispatch] = useReducer(reducer, initialState);
  const value = useMemo(() => [controller, dispatch], [controller, dispatch]);
  return <MaterialUI.Provider value={value}>{children}</MaterialUI.Provider>;
}
function useMaterialUIController() {
  const context = useContext(MaterialUI);
  if (!context) throw new Error("useMaterialUIController should be used inside the MaterialUIControllerProvider.");
  return context;
}
MaterialUIControllerProvider.propTypes = { children: PropTypes.node.isRequired };
const setMiniSidenav = (dispatch, value) => dispatch({ type: "MINI_SIDENAV", value });
const setTransparentSidenav = (dispatch, value) => dispatch({ type: "TRANSPARENT_SIDENAV", value });
const setWhiteSidenav = (dispatch, value) => dispatch({ type: "WHITE_SIDENAV", value });
const setSidenavColor = (dispatch, value) => dispatch({ type: "SIDENAV_COLOR", value });
const setTransparentNavbar = (dispatch, value) => dispatch({ type: "TRANSPARENT_NAVBAR", value });
const setFixedNavbar = (dispatch, value) => dispatch({ type: "FIXED_NAVBAR", value });
const setOpenConfigurator = (dispatch, value) => dispatch({ type: "OPEN_CONFIGURATOR", value });
const setDirection = (dispatch, value) => dispatch({ type: "DIRECTION", value });
const setLayout = (dispatch, value) => dispatch({ type: "LAYOUT", value });
const setDarkMode = (dispatch, value) => dispatch({ type: "DARKMODE", value });
export { AuthContextProvider, MaterialUIControllerProvider, useMaterialUIController,
  setMiniSidenav, setTransparentSidenav, setWhiteSidenav, setSidenavColor, setTransparentNavbar,
  setFixedNavbar, setOpenConfigurator, setDirection, setLayout, setDarkMode };
