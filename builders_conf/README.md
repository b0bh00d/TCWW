# Team City Builders
Each builder that will employ the WarningWatcher step must be represented by
name in this folder.  There are per-builder settings required for successful
step completion.

## Builder Config File
The builder that will use WarningWatcher must have an XML file in this folder,
named after the builder itself.  For example, if you have a builder called
"PowerEdgeWindows" that you plan to have run a WarningWatcher step, you will
need a file called "PowerEdgeWindows.xml" in this folder.

## Builder Config Settings
Each builder config file needs to provide certain environment-specific settings
for the WarningWatcher to function properly.  These settings are stored in XML
format.

A sample configuration for the aforementioned "PowerEdgeWindows" might look
like:

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <TCWW>
    <Settings>
      <Cache value="C:/TCWW"/>
      <AgentPath value="C:/TeamCity/buildAgent"/>
      <WarningRegex value=".+\(\d+\) : warning C\d+:"/>
    </Settings>
  </TCWW>
  ```

### Cache
The **Cache** setting lets the WarningWatcher know where it can store its cached
collection of build warnings.  If this setting is not specified, then the
system 'temp' location will be used.  **_Please note_**: Under TeamCity, this
system-defined 'temp' location will likely point to somewhere within the
build agent's install folder, and may (read: will) be deleted arbitrarily, so
your cache will be destroyed.  It is better if you point this value somewhere
outside the TeamCity build agent's folder.

Instead of a local path, you may also point the **Cache** at an offsite location
which makes it convenient when using a pool of builders.  One type of offsite
storage supported is FTP.  You can specify a valid FTP URL for the **Cache**
value.  If the FTP site requires a specific login in order to allow uploads,
you must include the username and password in the URL; e.g.:

  ```xml
  <Cache value="ftp://myusername:mypassword@ftp.location.com/TCWW"/>
  ```

If you have installed the Dropbox module into your working Python, and you have
an authorized Dropbox App token, you can specify this storage type in the
**Cache** setting by prefixing the path on Dropbox with "dropbox:" and providing
your access token, terminated with another colon; e.g.:

  ```xml
  <Cache value="dropbox:<app-access-token>:/TCWW"/>
  ```

### Agent Path
The **AgentPath** setting points at the TeamCity build agent path.  This path
should contain a "log/" sub-folder where build output is stored.

### Warning Detection
Detecting new warnings, or warnings that no longer appear, in the build output
is not as easy as it might seem at first glance.  Things like line numbers and
threaded building can make it next to impossible to accurately detect the
presence of new warning lines, or the absence of previous lines.  The
WarningWatcher system provides several techniques for identifying lines that
are compiler-generated warning messages, listed here in order from least
accurate to most.

Only one type can be active for a builder, and for the most consistent results,
all builders sharing the same cache file should use the same detection type.

#### WarningText
Each builder needs to have a means if identifying warning messages.  There are
several methods available for identifying compiler-generated output lines as
warning messages, each providing successfully finer and more accurate results.

The first is **WarningText**, which specifies a simple string fragment to be
located within each line.  If the provided fragment is detected in a line, it
is assumed that that line is a compiler-generated warning message.

#### WarningRegex
The second (illustrated in the XML code above) is **WarningRegex**.  This type
provides a finer granularity on detecting a line as a warning message.  The
example shown in the sample builder configuration above will identify Visual
Studio-formatted warning messages in the build output.  An example for GCC might
be:

  ```xml
    <WarningRegex value=".+:\d+:\d+: warning: "/>
  ```

#### WarningFormat
The last gives full "auto-detect" responsibility for detected warning messages
in the output over to the WarningWatcher system itself.  While this provides
ease-of-use for you, it also allows the WarningWatcher to perform certain
transformations on the identified lines such that the resulting output is as
accurate as it can possibly be.

The "auto-detect" type is named **WarningFormat**, and its value is the name of
the compiler that is generating the output.  For example, the Microsoft compiler
used by Visual Studio can be specified with:

  ```xml
    <WarningFormat value="microsoft"/>
  ```

or

  ```xml
    <WarningFormat value="visualstudio"/>
  ```

The GCC compiler form of warning message lines can be specified using:

  ```xml
    <WarningFormat value="gcc"/>
  ```

As these two generate the most common forms of compiler output, and are the
two compilers used on the project where I employ WarningWatcher, they are
currently the only two defined for the **WarningFormat** directive.