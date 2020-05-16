import React from "react";
import { Provider } from "react-redux";
import thunkMiddleware from "redux-thunk";
import { createBrowserHistory } from "history";
import { createStore, applyMiddleware } from "redux";
import { Router, Route, Switch } from "react-router-dom";

import rootReducer from "./reducers";
import indexRoutes from "./routes";
import "./style.css";

const hist = createBrowserHistory();
const store = createStore(rootReducer, applyMiddleware(thunkMiddleware));

export default function App() {
  return (
    <Provider store={store}>
      <Router history={hist}>
        <Switch>
          {indexRoutes.map((prop, key) => {
            return (
              <Route path={prop.path} component={prop.component} key={key} />
            );
          })}
        </Switch>
      </Router>
    </Provider>
  );
}
