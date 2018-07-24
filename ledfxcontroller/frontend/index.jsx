import React from "react";
import ReactDOM from "react-dom";
import { createBrowserHistory } from "history";
import { Router, Route, Switch } from "react-router-dom";

import "frontend/style.css"
import indexRoutes from "frontend/routes";

const hist = createBrowserHistory();


ReactDOM.render(
  <Router history={hist}>
    <Switch>
      {
        indexRoutes.map((prop, key) => {
            return <Route path={prop.path} component={prop.component} key={key} />;
        })
      }
    </Switch>
  </Router>,
  document.getElementById('main')
);
