const guideSidebar = [{ text: 'Usage Guide', link: '/guide/' }]

module.exports = {
  title: 'Arcsecond CLI',
  description: 'The command-line / Python module of Arcsecond.io.',
  base: '/',
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Install & Setup', link: '/install/' },
      { text: 'Basic Usage Guide', link: '/guide/' },
      { text: 'Plan Observations', link: '/observations/' }
    ],
    sidebar: {
      '/guide/': guideSidebar
    }
  }
}


