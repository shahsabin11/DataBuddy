# What DataBuddy is

DataBuddy is a web app for research students. A student uploads a spreadsheet, says what question they are trying to answer, and works with an AI partner. The partner does the mechanical work: cleaning, running the numbers, and formatting plots and tables. The student makes the judgment calls: which variables matter, which test to use, and what the result means.

The first version does three things. It cleans a file, it makes charts so the student can see the data, and it can run one comparison or regression and produce a report. A chart can be the whole task. A model is optional. It is aimed at biology, psychology, economics, anthropology, physics, chemistry, and geosciences. A typical file is a few hundred to about 80,000 rows.

## Who decides

The AI recommends. The student decides.

Safe cleanup, such as trimming blank space or dropping empty rows, is done automatically and written down so it can be undone. Anything that changes the results, such as deleting outliers, filling in missing values, or recoding categories, waits for the student.

The AI suggests a statistical test, explains the trade-off, and names one or two alternatives. It runs a test only after the student picks it. It does the same for charts: it recommends a chart type for the variables the student named, and it draws the figure only after the student agrees. It does not quietly drop variables, switch to a one-sided test after seeing the result, or claim that a result is causal.

Every step records what happened, why, what else was possible, and who chose it.

## What the first version can show and analyze

Students can ask for a histogram, a box plot, a bar chart, or a scatter plot without running a test. Those pictures are how they explore the file. If the standard chart is not the layout they need, they can approve a short plotting script. That script can change the look of the figure. It cannot invent a test result.

The tests are group comparisons, correlations, chi-square tests, and linear or yes/no regression. That covers the usual course project: compare two or more groups, see whether two measures move together, or fit a straightforward model. A test run also saves the charts that belong with it, such as a residual plot after a regression.

If a student asks for something beyond that, such as mixed models, time series, survival analysis, or machine learning, the app says no, points them to their advisor or campus stats consulting, and logs the request. It does not attempt a half version.

## How it is built

Students use a chat-style website. They sign in with Google or Microsoft. The site talks to a Python server, which is also the language used for the statistics. The AI plans the next step through a short list of tools. It does not get an open-ended coding agent.

The numbers are computed in a separate locked-down computer, not on the main server. That computer has no internet, no passwords, and no one else's files. It is thrown away after each step. Official test results come from functions we wrote and tested. The AI may write short cleaning or chart code, but only with ordinary table and plotting tools, and only after the student approves it. A cleaning script that changes the data is applied only after the student sees what changed.

Files live in cloud storage. The database stores the account, the project, the cleaning history, and the results. The original upload is never overwritten. Undo goes back one step.

The app runs on one small server. The whole term, including building, hosting, the domain, and AI usage, is planned inside a $1,120 budget. The pilot is one campus, about five students, for ten weeks.

## Many universities

Every campus shares one database. Each campus is a row, not a separate copy of the app. A university can have more than one email domain, such as `@uni.edu` and `@students.uni.edu`. People with a personal email, or a domain we have not set up yet, wait for an admin to approve them.

Students see their own projects. A campus admin can see that campus's projects and usage, and can approve people there. They do not read someone else's data files unless they were added to that project, or they record a reason. Adding a new university later is data entry, not a code change. One campus's rows are never returned to another campus.

## What we are not doing yet

We are not building a general data-science notebook, a machine-learning product, an interactive dashboard, maps, or a separate system per university. Deeper methods and stricter rules about keeping data inside one geographic region can come later. If a campus requires data to stay in one region, this version will refuse the upload rather than pretend it can guarantee that.
