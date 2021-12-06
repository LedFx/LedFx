import React from 'react';
import DataRow from './DataRow';

const IntegrationRow = ({ installedIntegrations, installedIntegration }) =>
    installedIntegrations[installedIntegration] &&
    installedIntegrations[installedIntegration].data &&
    installedIntegrations[installedIntegration].data.length > 0 ? (
        <DataRow
            id={installedIntegrations[installedIntegration].id}
            name={installedIntegrations[installedIntegration].config.name}
            type={installedIntegrations[installedIntegration].type}
            data={installedIntegrations[installedIntegration].data}
        />
    ) : (
        <></>
    );

export default IntegrationRow;
