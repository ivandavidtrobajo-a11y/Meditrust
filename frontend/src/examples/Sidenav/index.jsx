import { useEffect } from "react";
import { useLocation, NavLink } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "context";
import PropTypes from "prop-types";
import List from "@mui/material/List";
import Divider from "@mui/material/Divider";
import Link from "@mui/material/Link";
import Icon from "@mui/material/Icon";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useTheme } from "@mui/material/styles";
import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import SidenavCollapse from "examples/Sidenav/SidenavCollapse";
import SidenavRoot from "examples/Sidenav/SidenavRoot";
import sidenavLogoLabel from "examples/Sidenav/styles/sidenav";
import {
  useMaterialUIController,
  setMiniSidenav,
  setTransparentSidenav,
  setWhiteSidenav,
} from "context";

function Sidenav({ color, brand, brandName, routes, ...rest }) {
  const authContext = useContext(AuthContext);
  const visibleRoutes = routes.filter(
    (item) => !item.allowedRoles || item.allowedRoles.includes(authContext.user?.role)
  );
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode, sidenavColor } = controller;
  const location = useLocation();
  const theme = useTheme();
  const isMobileDrawer = useMediaQuery(theme.breakpoints.down("xl"));

  let textColor = "white";
  if (transparentSidenav || (whiteSidenav && !darkMode)) textColor = "dark";
  else if (whiteSidenav && darkMode) textColor = "inherit";

  const closeSidenav = () => setMiniSidenav(dispatch, true);
  const isRouteActive = (route) =>
    Boolean(route && (location.pathname === route || location.pathname.startsWith(`${route}/`)));

  useEffect(() => {
    function handleMiniSidenav() {
      const compact = window.innerWidth < 1200;
      setMiniSidenav(dispatch, compact);
      setTransparentSidenav(dispatch, compact ? false : transparentSidenav);
      setWhiteSidenav(dispatch, compact ? false : whiteSidenav);
    }
    handleMiniSidenav();
    window.addEventListener("resize", handleMiniSidenav);
    return () => window.removeEventListener("resize", handleMiniSidenav);
  }, [dispatch, location.pathname, transparentSidenav, whiteSidenav]);

  const renderRoutes = visibleRoutes.map(
    ({ type, name, icon, title, key, href, route }) => {
      if (type === "collapse") {
        const itemKey = key || route || href || name;
        return (
          <SidenavCollapse
            key={itemKey}
            component={href ? Link : NavLink}
            to={href ? undefined : route}
            href={href}
            target={href ? "_blank" : undefined}
            rel={href ? "noreferrer" : undefined}
            onClick={isMobileDrawer && !href ? closeSidenav : undefined}
            name={name}
            icon={icon}
            active={isRouteActive(route)}
          />
        );
      }
      if (type === "title") {
        return (
          <MDTypography
            key={key || title}
            color={textColor}
            display="block"
            variant="caption"
            fontWeight="bold"
            textTransform="uppercase"
            pl={3}
            mt={2}
            mb={1}
            ml={1}
          >
            {title}
          </MDTypography>
        );
      }
      if (type === "divider") {
        return (
          <Divider
            key={key || "sidenav-divider"}
            light={
              (!darkMode && !whiteSidenav && !transparentSidenav) ||
              (darkMode && !transparentSidenav && whiteSidenav)
            }
          />
        );
      }
      return null;
    }
  );

  const renderExampleRoutes = visibleRoutes.map(({ type, name, icon, key, href, route }) => {
    if (type !== "examples") return null;
    const itemKey = key || route || href || name;
    return (
      <SidenavCollapse
        key={itemKey}
        component={href ? Link : NavLink}
        to={href ? undefined : route}
        href={href}
        target={href ? "_blank" : undefined}
        rel={href ? "noreferrer" : undefined}
        onClick={isMobileDrawer && !href ? closeSidenav : undefined}
        name={name}
        icon={icon}
        active={isRouteActive(route)}
      />
    );
  });

  return (
    <SidenavRoot
      {...rest}
      variant={isMobileDrawer ? "temporary" : "permanent"}
      open={isMobileDrawer ? !miniSidenav : true}
      onClose={closeSidenav}
      ModalProps={{ keepMounted: true }}
      ownerState={{ transparentSidenav, whiteSidenav, miniSidenav, darkMode }}
    >
      <MDBox pt={3} pb={1} px={3} textAlign="center" position="relative">
        {isMobileDrawer && (
          <MDBox
            position="absolute"
            top={0}
            right={0}
            p={1.5}
            onClick={closeSidenav}
            sx={{ cursor: "pointer" }}
          >
            <MDTypography variant="h6" color="secondary">
              <Icon>close</Icon>
            </MDTypography>
          </MDBox>
        )}
        <MDBox
          component={NavLink}
          to="/"
          display="flex"
          alignItems="center"
          justifyContent="center"
          onClick={isMobileDrawer ? closeSidenav : undefined}
        >
          {brand && <MDBox component="img" src={brand} alt="Brand" width="2rem" />}
          <MDBox
            width={!brandName && "100%"}
            sx={(currentTheme) =>
              sidenavLogoLabel(currentTheme, {
                miniSidenav: isMobileDrawer ? false : miniSidenav,
              })
            }
          >
            <MDTypography component="h6" variant="button" fontWeight="medium" color={textColor}>
              {brandName}
            </MDTypography>
          </MDBox>
        </MDBox>
      </MDBox>
      <Divider
        light={
          (!darkMode && !whiteSidenav && !transparentSidenav) ||
          (darkMode && !transparentSidenav && whiteSidenav)
        }
      />
      <List sx={{ px: 1, pb: 2 }}>
        {visibleRoutes.some((item) => item.type === "examples") && (
          <>
            <MDBox display="flex" flexDirection="column" alignItems="stretch">
              <MDTypography
                color={textColor}
                variant="caption"
                fontWeight="medium"
                pl="1.5rem"
                py={1}
              >
                Usuarios
              </MDTypography>
              {renderExampleRoutes}
            </MDBox>
            <Divider
              sx={{ my: 1 }}
              light={
                (!darkMode && !whiteSidenav && !transparentSidenav) ||
                (darkMode && !transparentSidenav && whiteSidenav)
              }
            />
          </>
        )}
        {renderRoutes}
      </List>
    </SidenavRoot>
  );
}

Sidenav.defaultProps = { color: "info", brand: "" };
Sidenav.propTypes = {
  color: PropTypes.oneOf(["primary", "secondary", "info", "success", "warning", "error", "dark"]),
  brand: PropTypes.string,
  brandName: PropTypes.string.isRequired,
  routes: PropTypes.arrayOf(PropTypes.object).isRequired,
};
export default Sidenav;
