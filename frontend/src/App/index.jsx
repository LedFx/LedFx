import React from 'react';
import { Provider } from 'react-redux';
import { Router, Route, Switch } from 'react-router-dom';
import { MuiThemeProvider } from '@material-ui/core/styles';
import CssBaseline from '@material-ui/core/CssBaseline';

import indexRoutes from 'routes';
import createStore, { history } from './createStore';
import defaultTheme from './theme';
import './style.css';

const store = createStore();

export default function App() {
    return (
        <Provider store={store}>
            <CssBaseline />
            <MuiThemeProvider theme={defaultTheme}>
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
        </Provider>
    );
}
