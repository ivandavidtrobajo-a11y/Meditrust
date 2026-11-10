import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import PropTypes from "prop-types";
import MDBox from "components/MDBox";
import { useMaterialUIController, setLayout } from "context";

function DashboardLayout({ children }) {
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav } = controller;
  const { pathname } = useLocation();

  useEffect(() => {
    setLayout(dispatch, "dashboard");
  }, [pathname, dispatch]);

  return (
    <MDBox
      sx={({ breakpoints, transitions, functions: { pxToRem } }) => ({
        width: "100%",
        minWidth: 0,
        boxSizing: "border-box",
        p: { xs: 1.5, sm: 2, md: 3 },
        pt: { xs: 2, md: 3 },
        pb: { xs: 3, md: 3 },
        position: "relative",
        overflowX: "clip",
        [breakpoints.up("xl")]: {
          marginLeft: miniSidenav ? pxToRem(120) : pxToRem(274),
          width: miniSidenav ? `calc(100% - ${pxToRem(120)})` : `calc(100% - ${pxToRem(274)})`,
          transition: transitions.create(["margin-left", "width"], {
            easing: transitions.easing.easeInOut,
            duration: transitions.duration.standard,
          }),
        },
      })}
    >
      {children}
    </MDBox>
  );
}

DashboardLayout.propTypes = { children: PropTypes.node.isRequired };
export default DashboardLayout;
