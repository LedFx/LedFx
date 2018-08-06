import React from "react";
import ReactDOM from "react-dom";
import { Provider } from 'react-redux';
import thunkMiddleware from 'redux-thunk'
import rootReducer from 'frontend/reducers';
import { createBrowserHistory } from "history";
import { createStore, applyMiddleware } from 'redux'
import { Router, Route, Switch } from "react-router-dom";

import "frontend/style.css";
import indexRoutes from "frontend/routes";

const hist = createBrowserHistory();
const store = createStore(rootReducer,
  applyMiddleware(
    thunkMiddleware
  ));

ReactDOM.render(
  <Provider store={store}>
    <Router history={hist}>
      <Switch>
        {
          indexRoutes.map((prop, key) => {
              return <Route path={prop.path} component={prop.component} key={key} />;
          })
        }
      </Switch>
    </Router>
  </Provider>,
  document.getElementById('main')
);
