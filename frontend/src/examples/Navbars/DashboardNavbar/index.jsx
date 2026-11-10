import { useState, useEffect, useContext } from "react";
import { useLocation, Link, useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import Icon from "@mui/material/Icon";
import MDBox from "components/MDBox";
import MDInput from "components/MDInput";
import Breadcrumbs from "examples/Breadcrumbs";
import NotificationItem from "examples/Items/NotificationItem";
import AuthService from "services/auth-service";
import {
  navbar, navbarContainer, navbarRow, navbarIconButton, navbarMobileMenu,
} from "examples/Navbars/DashboardNavbar/styles";
import {
  useMaterialUIController, setTransparentNavbar, setMiniSidenav, setOpenConfigurator,
} from "context";
import MDButton from "components/MDButton";
import { AuthContext } from "context";

function DashboardNavbar({ absolute, light, isMini }) {
  const authContext = useContext(AuthContext);
  const [navbarType, setNavbarType] = useState("static");
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav, transparentNavbar, fixedNavbar, openConfigurator, darkMode } = controller;
  const [openMenu, setOpenMenu] = useState(null);
  const route = useLocation().pathname.split("/").slice(1);
  const navigate = useNavigate();

  useEffect(() => {
    setNavbarType(fixedNavbar ? "sticky" : "static");
    function handleTransparentNavbar() {
      setTransparentNavbar(dispatch, (fixedNavbar && window.scrollY === 0) || !fixedNavbar);
    }
    window.addEventListener("scroll", handleTransparentNavbar);
    handleTransparentNavbar();
    return () => window.removeEventListener("scroll", handleTransparentNavbar);
  }, [dispatch, fixedNavbar]);

  const handleMiniSidenav = () => setMiniSidenav(dispatch, !miniSidenav);
  const handleConfiguratorOpen = () => setOpenConfigurator(dispatch, !openConfigurator);
  const handleOpenMenu = (event) => setOpenMenu(event.currentTarget);
  const handleCloseMenu = () => setOpenMenu(null);

  const renderMenu = () => (
    <Menu
      anchorEl={openMenu}
      anchorReference={null}
      anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      open={Boolean(openMenu)}
      onClose={handleCloseMenu}
      sx={{ mt: 2 }}
    >
      <NotificationItem icon={<Icon>email</Icon>} title="Check new messages" />
      <NotificationItem icon={<Icon>podcasts</Icon>} title="Manage Podcast sessions" />
      <NotificationItem icon={<Icon>shopping_cart</Icon>} title="Payment successfully completed" />
    </Menu>
  );

  const iconsStyle = ({ palette: { dark, white, text }, functions: { rgba } }) => ({
    color: () => {
      let colorValue = light || darkMode ? white.main : dark.main;
      if (transparentNavbar && !light) colorValue = darkMode ? rgba(text.main, 0.6) : text.main;
      return colorValue;
    },
  });

  const handleLogOut = async () => {
    await AuthService.logout();
    authContext.logout();
    navigate("/auth/login");
  };

  return (
    <AppBar
      position={absolute ? "absolute" : navbarType}
      color="inherit"
      sx={(currentTheme) => navbar(currentTheme, { transparentNavbar, absolute, light, darkMode })}
    >
      <Toolbar sx={(currentTheme) => navbarContainer(currentTheme)}>
        <MDBox color="inherit" sx={(currentTheme) => navbarRow(currentTheme, { isMini })}>
          <Breadcrumbs icon="home" title={route[route.length - 1]} route={route} light={light} />
        </MDBox>
        {!isMini && (
          <MDBox sx={(currentTheme) => navbarRow(currentTheme, { isMini })}>
            <MDBox pr={1} sx={{ display: { xs: "none", sm: "block" } }}>
              <MDInput label="Buscar" />
            </MDBox>
            <MDBox display="flex" alignItems="center" color={light ? "white" : "inherit"}>
              <Link to="/user-profile" aria-label="Perfil">
                <IconButton sx={navbarIconButton} size="small" disableRipple aria-label="Perfil">
                  <Icon sx={iconsStyle}>account_circle</Icon>
                </IconButton>
              </Link>
              <IconButton
                size="small"
                disableRipple
                color="inherit"
                sx={navbarMobileMenu}
                onClick={handleMiniSidenav}
                aria-label={miniSidenav ? "Abrir navegación" : "Cerrar navegación"}
              >
                <Icon sx={iconsStyle} fontSize="medium">
                  {miniSidenav ? "menu" : "menu_open"}
                </Icon>
              </IconButton>
              <IconButton
                size="small"
                disableRipple
                color="inherit"
                sx={navbarIconButton}
                onClick={handleConfiguratorOpen}
                aria-label="Configuración visual"
              >
                <Icon sx={iconsStyle}>settings</Icon>
              </IconButton>
              <IconButton
                size="small"
                disableRipple
                color="inherit"
                sx={{ ...navbarIconButton, display: { xs: "none", sm: "inline-flex" } }}
                aria-controls="notification-menu"
                aria-haspopup="true"
                onClick={handleOpenMenu}
                aria-label="Notificaciones"
              >
                <Icon sx={iconsStyle}>notifications</Icon>
              </IconButton>
              {renderMenu()}
              <MDBox>
                <MDButton variant="gradient" color="info" size="small" type="button" onClick={handleLogOut}>
                  Salir
                </MDButton>
              </MDBox>
            </MDBox>
          </MDBox>
        )}
      </Toolbar>
    </AppBar>
  );
}

DashboardNavbar.defaultProps = { absolute: false, light: false, isMini: false };
DashboardNavbar.propTypes = {
  absolute: PropTypes.bool,
  light: PropTypes.bool,
  isMini: PropTypes.bool,
};
export default DashboardNavbar;
