
import PropTypes from "prop-types";
import Grid from "@mui/material/Grid";
import { Typography, List, ListItem, ListItemText } from "@mui/material";
import { useLocation } from "react-router-dom";

import MDBox from "components/MDBox";
import DefaultNavbar from "examples/Navbars/DefaultNavbar";
import PageLayout from "examples/LayoutContainers/PageLayout";
import Footer from "layouts/authentication/components/Footer";

function BasicLayout({ image, children }) {
  const { pathname } = useLocation();

  return (
    <PageLayout>
      <DefaultNavbar
        action={{
          type: "external",
          route: "#",
          label: "Hola",
          color: "dark",
        }}
      />
      <MDBox
        sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}
        width="100%"
      >
        <MDBox
          position="relative"
          width="100%"
          minHeight="100vh"
          display="flex"
          flexDirection="column"
          sx={{
            backgroundImage: ({ functions: { linearGradient, rgba }, palette: { gradients } }) =>
              image &&
              `${linearGradient(
                rgba(gradients.dark.main, 0.6),
                rgba(gradients.dark.state, 0.6)
              )}, url(${image})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat",
            flex: "1 0 auto",
          }}
        >
          <MDBox
            position="relative"
            display="flex"
            flexDirection="column"
            justifyContent="center"
            width="100%"
            sx={{ flex: "1 0 auto", paddingTop: "4em" }}
          >
            <MDBox paddingBottom="3rem" sx={{ textAlign: "center" }}>
              {pathname === "/auth/login" && (
                <MDBox display="flex" width="100%" justifyContent="center" sx={{ zIndex: 99 }}>
                  <MDBox
                    display="flex"
                    flexDirection="column"
                    justifyContent="center"
                    alignItems="center"
                    padding="1.5rem"
                    width="80%"
                  >
                    <Typography variant="h3" sx={{ color: "white" }}>
                      Iniciar sesión — Sistema Médico
                    </Typography>
                    <Typography variant="body2" sx={{ color: "white" }} margin="0.5rem 0">
                      Inicia sesión con tu cuenta
                    </Typography>
                    <MDBox
                      display="flex"
                      flexDirection="column"
                      justifyContent="center"
                      alignItems="center"
                      marginBottom="0.5rem"
                    >
                      <List dense>
                        <ListItem>
                          <ListItemText
                            disableTypography
                            primary={<Typography variant="body2" fontWeight="400" sx={{ color: "white" }} />}
                          />
                        </ListItem>
                      </List>
                    </MDBox>
                  </MDBox>
                </MDBox>
              )}
              <MDBox px={1} width="100%" mx="auto" paddingTop="1rem">
                <Grid container spacing={1} justifyContent="center" alignItems="center">
                  <Grid item xs={11} sm={9} md={5} lg={4} xl={3}>
                    {children}
                  </Grid>
                </Grid>
              </MDBox>
            </MDBox>
          </MDBox>
          <Footer light />
        </MDBox>
      </MDBox>
    </PageLayout>
  );
}

BasicLayout.propTypes = {
  image: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
};

export default BasicLayout;
