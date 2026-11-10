import PropTypes from "prop-types";
import Box from "@mui/material/Box";

function ResponsiveSection({ children, spacing, ...rest }) {
  return (
    <Box
      component="section"
      sx={{
        width: "100%",
        minWidth: 0,
        mb: spacing,
        "& > *": { minWidth: 0 },
      }}
      {...rest}
    >
      {children}
    </Box>
  );
}

ResponsiveSection.propTypes = {
  children: PropTypes.node.isRequired,
  spacing: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};
ResponsiveSection.defaultProps = { spacing: { xs: 2, md: 3 } };
export default ResponsiveSection;
