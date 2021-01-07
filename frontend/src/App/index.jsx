import React from 'react';
import { Provider } from 'react-redux';
import CssBaseline from '@material-ui/core/CssBaseline';
import createStore from './createStore';
import './style.css';
import Main from './App'

const store = createStore();

export default function App() {
    return (
        <Provider store={store}>
            <CssBaseline />
            <Main />
        </Provider>
    );
}
