import PropTypes from "prop-types";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

function ResponsivePageHeader({ title, description, action }) {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      alignItems={{ xs: "stretch", sm: "center" }}
      justifyContent="space-between"
      spacing={1.5}
      sx={{ mb: { xs: 2, md: 3 }, minWidth: 0 }}
    >
      <Stack spacing={0.5} sx={{ minWidth: 0 }}>
        <Typography variant="h5" component="h1" sx={{ color: "text.primary", fontWeight: 700 }}>
          {title}
        </Typography>
        {description && (
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        )}
      </Stack>
      {action && <Stack direction="row" alignItems="center" sx={{ flexShrink: 0 }}>{action}</Stack>}
    </Stack>
  );
}

ResponsivePageHeader.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  action: PropTypes.node,
};
ResponsivePageHeader.defaultProps = { description: "", action: null };
export default ResponsivePageHeader;
