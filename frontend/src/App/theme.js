import { createMuiTheme } from '@material-ui/core/styles';
import teal from '@material-ui/core/colors/teal';

export default createMuiTheme({
    palette: {
        primary: teal,
        secondary: {
          main: '#ef6c00',
        },
    },
    overrides: {
        MuiFormControl: {
            root: {
                margin: 8,
                minWidth: 225,
                flex: '1 0 30%',
            },
        },
    },
    props: {
        MuiCard: {
            variant: "outlined"
        }
    }
});
