import { createMuiTheme } from '@material-ui/core/styles';
import teal from '@material-ui/core/colors/teal';

export default createMuiTheme({
    palette: {
        primary: teal,
        secondary: {
            main: '#f05545',
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
            variant: 'outlined',
        },
    },
});

export const darkTheme = createMuiTheme({
    palette: {
        type: 'dark',
        primary: teal,
        secondary: {
            main: '#f05545',
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
            variant: 'outlined',
        },
    },
});
export const bladeTheme = createMuiTheme({
    palette: {
        primary: {
            main: '#800000',
        },
        secondary: {
            main: '#f05545',
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
            variant: 'outlined',
        },
    },
});

export const bladeDarkTheme = createMuiTheme({
    palette: {
        type: 'dark',
        primary: {
            main: '#600000',
        },
        secondary: {
            main: '#999',
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
            variant: 'outlined',
        },
    },
});
export const greenDarkTheme = createMuiTheme({
    palette: {
        type: 'dark',
        primary: {
            main: '#1db954',
        },
        secondary: {
            main: '#999',
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
            variant: 'outlined',
        },
    },
});
export const greenLightTheme = createMuiTheme({
    palette: {
        type: 'light',
        primary: {
            main: '#1db954',
        },
        secondary: {
            main: '#999',
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
            variant: 'outlined',
        },
    },
});
export const curacaoLightTheme = createMuiTheme({
    palette: {
        type: 'light',
        primary: {
            main: '#0dbedc',
        },
        secondary: {
            main: '#999',
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
            variant: 'outlined',
        },
    },
});
export const curacaoDarkTheme = createMuiTheme({
    palette: {
        type: 'dark',
        primary: {
            main: '#0dbedc',
        },
        secondary: {
            main: '#999',
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
            variant: 'outlined',
        },
    },
});
