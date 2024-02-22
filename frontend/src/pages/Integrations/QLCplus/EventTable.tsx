/* eslint-disable @typescript-eslint/indent */
// import DataRow from './DataRow';

const IntegrationRow = ({
  installedIntegrations,
  installedIntegration
}: any) =>
  installedIntegrations[installedIntegration] &&
  installedIntegrations[installedIntegration].data &&
  installedIntegrations[installedIntegration].data.length > 0
    ? 'coming soon'
    : //   <DataRow
      //   id={installedIntegrations[installedIntegration].id}
      //   name={installedIntegrations[installedIntegration].config.name}
      //   type={installedIntegrations[installedIntegration].type}
      //   data={installedIntegrations[installedIntegration].data}
      // />
      null

export default IntegrationRow
