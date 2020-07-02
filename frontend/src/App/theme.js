import { createMuiTheme } from '@material-ui/core/styles';
import cyan from '@material-ui/core/colors/cyan';
import green from '@material-ui/core/colors/green';

export default createMuiTheme({
    palette: {
        primary: cyan,
        secondary: green,
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
