import { useEffect } from "react";
import { useLocation, NavLink } from "react-router-dom";
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
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode, sidenavColor } = controller;
  const location = useLocation();
  const theme = useTheme();
  const isMobileDrawer = useMediaQuery(theme.breakpoints.down("xl"));
  const collapseName = location.pathname.replace("/", "");

  let textColor = "white";
  if (transparentSidenav || (whiteSidenav && !darkMode)) textColor = "dark";
  else if (whiteSidenav && darkMode) textColor = "inherit";

  const closeSidenav = () => setMiniSidenav(dispatch, true);

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
  }, [dispatch, location.pathname]);

  const renderRoutes = routes.map(({ type, name, icon, title, noCollapse, key, href, route }) => {
    if (type === "collapse") {
      return href ? (
        <Link href={href} key={key} target="_blank" rel="noreferrer" sx={{ textDecoration: "none" }}>
          <SidenavCollapse name={name} icon={icon} active={key === collapseName} noCollapse={noCollapse} />
        </Link>
      ) : (
        <NavLink key={key} to={route} onClick={isMobileDrawer ? closeSidenav : undefined}>
          <SidenavCollapse name={name} icon={icon} active={key === collapseName} />
        </NavLink>
      );
    }
    if (type === "title") {
      return (
        <MDTypography key={key} color={textColor} display="block" variant="caption"
          fontWeight="bold" textTransform="uppercase" pl={3} mt={2} mb={1} ml={1}>
          {title}
        </MDTypography>
      );
    }
    if (type === "divider") {
      return <Divider key={key} light={(!darkMode && !whiteSidenav && !transparentSidenav) ||
        (darkMode && !transparentSidenav && whiteSidenav)} />;
    }
    return null;
  });

  const renderExampleRoutes = routes.map(({ type, name, icon, noCollapse, key, href, route }) => {
    if (type !== "examples") return null;
    return href ? (
      <Link href={href} key={key} target="_blank" rel="noreferrer" sx={{ textDecoration: "none" }}>
        <SidenavCollapse name={name} icon={icon} active={key === collapseName} noCollapse={noCollapse} />
      </Link>
    ) : (
      <NavLink key={key} to={route} onClick={isMobileDrawer ? closeSidenav : undefined}>
        <SidenavCollapse name={name} icon={icon} active={key === collapseName} />
      </NavLink>
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
          <MDBox position="absolute" top={0} right={0} p={1.5} onClick={closeSidenav} sx={{ cursor: "pointer" }}>
            <MDTypography variant="h6" color="secondary"><Icon>close</Icon></MDTypography>
          </MDBox>
        )}
        <MDBox component={NavLink} to="/" display="flex" alignItems="center" justifyContent="center"
          onClick={isMobileDrawer ? closeSidenav : undefined}>
          {brand && <MDBox component="img" src={brand} alt="Brand" width="2rem" />}
          <MDBox width={!brandName && "100%"} sx={(currentTheme) => sidenavLogoLabel(currentTheme, { miniSidenav: isMobileDrawer ? false : miniSidenav })}>
            <MDTypography component="h6" variant="button" fontWeight="medium" color={textColor}>
              {brandName}
            </MDTypography>
          </MDBox>
        </MDBox>
      </MDBox>
      <Divider light={(!darkMode && !whiteSidenav && !transparentSidenav) ||
        (darkMode && !transparentSidenav && whiteSidenav)} />
      <List sx={{ px: 1, pb: 2 }}>
        <MDBox display="flex" flexDirection="column" alignItems="stretch">
          <MDTypography color={textColor} variant="caption" fontWeight="medium" pl="1.5rem" py={1}>
            Usuarios
          </MDTypography>
          {renderExampleRoutes}
        </MDBox>
        <Divider sx={{ my: 1 }} light={(!darkMode && !whiteSidenav && !transparentSidenav) ||
          (darkMode && !transparentSidenav && whiteSidenav)} />
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
