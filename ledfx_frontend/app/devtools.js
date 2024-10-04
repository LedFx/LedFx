const installDevtools = async (installExtension) =>
  await installExtension(
    ['lmhkpmbekcpmknklioeibfkpmmfibljd', 'fmkadmapgofadopljbjfkapdkoienihi'],
    {
      loadExtensionOptions: { allowFileAccess: true },
      forceDownload: false
    }
  )
    .then((name) => console.log(`Added Extension:  ${name}`))
    .catch((error) => console.log(`An error occurred: , ${error}`))

module.exports = { installDevtools }
