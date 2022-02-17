import React from 'react';
import { Router, Route, Switch } from 'react-router-dom';
import { MuiThemeProvider } from '@material-ui/core/styles';
// import { useSelector } from "react-redux"
import indexRoutes from 'routes';
import { history } from './createStore';
import defaultTheme, {
    darkTheme,
    bladeTheme,
    bladeDarkTheme,
    greenLightTheme,
    greenDarkTheme,
    curacaoLightTheme,
    curacaoDarkTheme,
} from './theme';
// import { createMuiTheme } from '@material-ui/core/styles';
import './style.css';
import './materialdesignicons.css';
import 'react-toastify/dist/ReactToastify.css';
import SnackbarDynamic from '../components/SnackbarDynamic';

export default function App() {
    // const themeSelector = useSelector(state => state.themeSelector)

    const theme =
        window.localStorage.getItem('blade') === '1'
            ? darkTheme
            : window.localStorage.getItem('blade') === '2'
            ? bladeTheme
            : window.localStorage.getItem('blade') === '3'
            ? bladeDarkTheme
            : window.localStorage.getItem('blade') === '4'
            ? greenLightTheme
            : window.localStorage.getItem('blade') === '5'
            ? greenDarkTheme
            : window.localStorage.getItem('blade') === '6'
            ? curacaoLightTheme
            : window.localStorage.getItem('blade') === '7'
            ? curacaoDarkTheme
            : defaultTheme;

    return (
        <MuiThemeProvider theme={theme}>
            <SnackbarDynamic />
            <Router history={history}>
                <Switch>
                    {indexRoutes.map(({ component: Component, path }, key) => {
                        return (
                            <Route
                                path={path}
                                key={key}
                                render={routeProps => <Component {...routeProps} />}
                            />
                        );
                    })}
                </Switch>
            </Router>
        </MuiThemeProvider>
    );
}
